# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utilities to spell check schema nodes.


To spell check a list of MCF files, run the command:
  python schema_spell_checker.py --spell_input_mcf=<input-mcf-file> \
      --spell_error_output=<output-file-with-errors-per-node>
"""

import os
import re
import sys

from absl import app
from absl import flags
from absl import logging

from spellchecker import SpellChecker

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logging.info(f'DELETE ME: file: {__file__}, dir: {_SCRIPT_DIR}')
sys.path.append(_SCRIPT_DIR)
sys.path.append(os.path.dirname(_SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR))),
                 'util'))

_DEFAULT_ALLOWLIST = os.path.join(_SCRIPT_DIR, 'words_allowlist.txt')

flags.DEFINE_string('spell_input_mcf', '',
                    'MCF file with nodes to generate schema for.')
flags.DEFINE_string('spell_error_output', '', 'File with list of spell errors')
flags.DEFINE_string('spell_allowlist', _DEFAULT_ALLOWLIST,
                    'File with words to be allowed')
flags.DEFINE_string('spell_config', '', 'File with words to be allowed')
flags.DEFINE_bool('spell_check_text_only', False,
                  'if True, spell check quoted text values only.')

_FLAGS = flags.FLAGS

import config_flags
import file_util
import process_http_server

import property_value_utils as pv_utils

from config_map import ConfigMap
from counters import Counters
from config_map import ConfigMap
from mcf_file_util import load_mcf_nodes, write_mcf_nodes
from mcf_file_util import add_namespace, strip_namespace, add_mcf_node

# properties ignored for spell check
_DEFAULT_IGNORE_SPELL_PROPS = {
    # Ignore non-English property:values
    'nameWithLanguage',

    # Ignore values with URLs
    'url',
    'descriptionUrl',
    'license',
    'sourceDataUrl',
    'cachedSourceDataUrl',
    'dataTransformationLogic',

    # Ignore values with JSONs
    'geoJsonCoordinates',
    'geoJsonCoodinatesDP1',
    'geoJsonCoodinatesDP2',
    'geoJsonCoodinatesDP3',

    # Ignore properties with non-text values
    'keyString',
}


def get_words(value: str) -> list:
    """Returns a list of words from the value string.

  Args:
    value: string to be tokenized into words

  Returns:
    List of words
  """
    # Remove any extra characters
    value_str = re.sub('[^A-Za-z]', ' ', str(value))
    words = []
    for w in value_str.split(' '):
        if not w:
            continue

        # Split CamelCase into separate words
        split_pos = [0]
        split_pos.extend(
            [m.start() + 1 for m in re.finditer('[^A-Z][A-Z0-9]', w)])
        split_pos.append(len(w))
        words.extend(
            [w[start:end] for start, end in zip(split_pos, split_pos[1:])])

    # Remove acronyms that are fully capitalized
    text_words = []
    for w in words:
        if len(w) >= 2 and not (w[0].isupper() and w[1].isupper()):
            text_words.append(w)
    return text_words


def should_ignore_spell_pv(prop: str,
                           value: str,
                           config: ConfigMap = None) -> bool:
    """Returns True if the property:value should be ignored.
  values such as URLs or json objects are ignored.

  Args:
    prop: property string
    value: value of the property
    config: config map with settings:
      'spell_check_props': [] # list of properties to be checked.
      'spell_check_ignore_props': [] # list of properties to be ignored
      'spell_check_text_only': if True, only quoted values are checked
  Returns:
   True if the property:value should be ignored for spell check.
  """
    if not config:
        config = ConfigMap()

    # Ignore property that begins with '#'
    if not prop:
        return True

    if prop[0] == '#':
        return True

    if not pv_utils.is_valid_property(prop):
        return True

    # Ignore properties in ignore list.
    ignore_props = config.get('spell_check_ignore_props')
    if ignore_props is None:
        ignore_props = _DEFAULT_IGNORE_SPELL_PROPS

    if prop in ignore_props:
        return True

    # Ignore properties not listed in props to be checked.
    spell_props = config.get('spell_check_props', [])
    if spell_props and prop not in spell_props:
        return True

    if value and isinstance(value, str):
        # Ignore autogenerated ids that begins with dc/, such as,
        # dc/vp8cbt6k79t94 or dc/o/wjtdrd9wq4m2g
        # that don't have any capital letters.
        # Do not ignore human-generated ids such as dc/g/Root
        if "dc/" in value:
            capitals = [c for c in value if c.isupper()]
            if not capitals:
                return True

        # Check if only quoted values are to be checked.
        if '@' in value:
            # Ignore values with non-English strings like nameWithLanguage
            return True
        quoted_values_only = config.get('spell_check_text_only', False)
        if quoted_values_only and value[0] != '"':
            return True

        # Ignore values that are auto generated  Node values,
        # such as, E0/45f0043e-5a3c-1c95-ee38-79891bfe7b6f
        if re.search(r'\bE[0-9]+\b', value):
            return True
    return False


def spell_check_pvs(dcid: str,
                    node: dict,
                    spell_checker: SpellChecker,
                    config: ConfigMap = None,
                    counters: Counters = None) -> dict:
    """Spell check a node with property:values.

  Args:
    dcid: dcid for the MCF node.
    node: dictionary with property:value
    spell_checker: SpellChecker object

  Returns:
    Tuple of (misspelled_pvs, misspelled words), where
      misspelled_pvs is comma separated list of misspelled words per property
      and misspelled_words is a list of words with spell errors.

  """
    words_misspelled = set()
    misspelled_pvs = dict()
    for prop, value in node.items():
        if should_ignore_spell_pv(prop, value, config):
            if counters:
                counters.add_counter(f'spell-check-ignored-pvs', 1)
            continue
        # Get words from property and value
        pv_words = set()
        if not config.get('spell_check_text_only', False):
            if spell_checker.unknown([prop]):
                # Prop not in allow list. Check all words property.
                pv_words = set(get_words(prop))
        value = str(value)
        if spell_checker.unknown([value]):
            # Value not in allow list. Check all words in value.
            pv_words.update(get_words(strip_namespace(value)))
        # Spell check all words in this property:value
        if pv_words:
            error_words = spell_checker.unknown(pv_words)
            if error_words:
                #TODO: treat words with spell_checker.candidates()
                # alone as errors to reduce false positives.
                logging.error(f'SpellError: {dcid}:{prop}:{error_words}')
                words_misspelled.update(error_words)
                misspelled_pvs[prop] = ', '.join(sorted(error_words))
            if counters:
                counters.add_counter(f'spell-check-pvs', 1)
                if error_words:
                    counters.add_counter(f'spell-check-pvs-errors', 1)
    return misspelled_pvs, words_misspelled


def spell_check_nodes(nodes: dict,
                      config: ConfigMap = None,
                      counters: Counters = None,
                      spell_checker: SpellChecker = None) -> dict:
    """Spell check property:values in MCF nodes.

    Args:
      nodes: dictionary of nodes, each node as dictionary of property:value
      counters: counters to be updated
      spell_checker: SpellChecker object.
        If not set, a default SpellChecker is used.
      quoted_values_only: if True, only text within double-quote are checked.

    Returns:
     dictionary of spell errors keyed by dcid.
    """
    if counters is None:
        counters = Counters()
    if not config:
        config = ConfigMap()
    if not spell_checker:
        # Get a default SpellChecker
        spell_checker = get_spell_checker(config, counters)

    node_errors = {}
    error_words = set()
    # Spell check each node.
    for dcid, node in nodes.items():
        counters.add_counter('spell-check-nodes', 1)
        misspelled_pvs, misspelled_words = spell_check_pvs(
            dcid, node, spell_checker, config, counters)
        if misspelled_words:
            # Reccord errors for the node keyed by dcid.
            logging.error(f'SpellError: {dcid}: {misspelled_pvs}')
            node_errors[dcid] = misspelled_pvs
            error_words.update(misspelled_words)
            counters.add_counter(f'spell-check-nodes-errors', 1, dcid)
    if error_words:
        logging.error(f'Words with spell errors: {error_words}')
        counters.add_counter(f'error-spell-words', len(error_words))
    return node_errors


def spell_check_mcf(input_mcf: str,
                    config: ConfigMap = None,
                    counters: Counters = None) -> dict:
    """Spell checks dictionary of schema nodes.
  Each node is a dict of property: values.
  Sets counters for misspelled words.

  Args:
    input_mcf: MCF file with input nodes.

  Returns:
    dictionary of misspelled words per node.
  """
    if counters is None:
        counters = Counters()
    if not config:
        config = ConfigMap()

    logging.info(
        f'Spell check: {input_mcf} with config: {config.get_configs()}')
    spell_checker = get_spell_checker(config, counters)

    # Check spelling of each node in all MCF files.
    nodes_misspelled = {}
    input_files = file_util.file_get_matching(input_mcf)
    for mcf_file in input_files:
        logging.info(f'Loading MCF file: {mcf_file}')
        nodes = load_mcf_nodes(mcf_file)
        counters.add_counter(f'input-mcf-file', 1, mcf_file)
        counters.add_counter(f'total', len(nodes))
        node_errors = spell_check_nodes(nodes, config, counters, spell_checker)
        if node_errors:
            for dcid, error_pvs in node_errors.items():
                for prop, errors in error_pvs.items():
                    nodes_misspelled[len(nodes_misspelled)] = {
                        'file': mcf_file,
                        'dcid': dcid,
                        'property': prop,
                        'spell_errors': errors,
                    }
            counters.add_counter(f'files-with-spell-errors', 1, mcf_file)
        counters.add_counter(f'processed', len(nodes))
    output_file = config.get('spell_check_output', '')
    if nodes_misspelled and output_file:
        # Save misspelled words
        output_file = file_util.file_get_name(output_file, file_ext='')
        logging.info(
            f'Writing misspelled words in {len(nodes_misspelled)} nodes into: {output_file}'
        )
        file_util.file_write_py_dict(nodes_misspelled, output_file)

    return nodes_misspelled


def get_spell_checker(config: ConfigMap = None,
                      counters: Counters = None) -> SpellChecker:
    """Returns a SpellChecker object."""
    spell_checker = SpellChecker()
    if not config:
        config = ConfigMap(get_default_spell_config())
    allowlist_file = config.get('spell_allowlist', _DEFAULT_ALLOWLIST)
    allow_words = config.get('spell_allow_words', ['dcs', 'dcid'])
    initial_words = spell_checker.word_frequency.unique_words

    allow_files = file_util.file_get_matching(allowlist_file)
    for file in allow_files:
        logging.info(f'Loading allowed words from {file}')
        spell_checker.word_frequency.load_text_file(file)
        if counters:
            counters.add_counter(f'spell-allowlist-file', 1, file)

    if allow_words:
        if isinstance(allow_words, str):
            allow_words = allow_words.split(',')
        spell_checker.word_frequency.load_words(allow_words)

    num_words = spell_checker.word_frequency.unique_words - initial_words
    logging.info(
        f'Spell checker loaded with {num_words} words from {allowlist_file}')
    if counters:
        counters.add_counter(f'spell-allowlist-words', num_words,
                             allowlist_file)
    return spell_checker


def get_default_spell_config() -> dict:
    """Returns the config for spell checker from flags."""
    configs = {}
    if _FLAGS.spell_allowlist:
        configs['spell_allowlist'] = _FLAGS.spell_allowlist
    if _FLAGS.spell_error_output:
        configs['spell_check_output'] = _FLAGS.spell_error_output
    if _FLAGS.spell_check_text_only:
        configs['spell_check_text_only'] = _FLAGS.spell_check_text_only
    configs['spell_check_ignore_props'] = _DEFAULT_IGNORE_SPELL_PROPS
    return configs


def main(_):
    # Launch a web server with a form for commandline args
    # if the command line flag --http_port is set.
    if process_http_server.run_http_server(script=__file__, module=__name__):
        return

    config = ConfigMap()
    config.add_configs(
        config_flags.init_config_from_flags(_FLAGS.spell_config).get_configs())
    config.add_configs(get_default_spell_config())
    spell_check_mcf(_FLAGS.spell_input_mcf, config)


if __name__ == '__main__':
    app.run(main)
