"""The strict YAML subset reader refuses flow sequences YAML does not allow."""

import itertools
import unittest

import yaml

import bootstrap

# A lone "-" is a block sequence entry's indicator; YAML 1.2.2 (7.3.3, Plain
# Style, production 126) lets a plain scalar start with "-" only when a
# character it allows in a flow collection follows.
# PyYAML rejects these: the "-" is followed by a space.
PYYAML_REJECTS = ('[- , "a"]', "[ - ]", "[a, - ]")
# PyYAML accepts a "-" just before "," or "]", which the rule forbids too.
PYYAML_ADMITS = ("[-]", "[-, a]", "[a, -]", "[a,-]", "['a', -]", '[-,"a"]')
ADMITTED = {
    "[-a]": ["-a"],
    "[--x]": ["--x"],
    "[a-b, -c]": ["a-b", "-c"],
    "['-', \"-\"]": ["-", "-"],
    "[-.5x]": ["-.5x"],
    "[ push , workflow_call ]": ["push", "workflow_call"],
}


class FlowSequenceTests(unittest.TestCase):
    def test_a_lone_dash_item_is_refused(self):
        for text in PYYAML_REJECTS + PYYAML_ADMITS:
            with self.subTest(text=text):
                self.assertIsNone(bootstrap._value(text))
        for text in PYYAML_REJECTS:
            with self.subTest(text=text), self.assertRaises(yaml.YAMLError):
                yaml.safe_load(f"k: {text}\n")

    def test_dash_led_words_and_quoted_dashes_are_still_read(self):
        for text, items in ADMITTED.items():
            with self.subTest(text=text):
                value = bootstrap._value(text)
                self.assertEqual(value, text.strip())
                self.assertEqual(bootstrap._flow_items(value), items)
                self.assertEqual(yaml.safe_load(f"k: {text}\n")["k"], items)

    def test_every_short_flow_sequence_the_reader_admits_is_one_pyyaml_reads_the_same(self):
        # Every bracketed text of up to five characters from a small alphabet.
        # The reader may refuse more than PyYAML (it then refuses the file),
        # never less, and reads each admitted item's text as PyYAML does.
        alphabet = ["-", "a", ",", " ", '"', "'", ".", "#"]
        admitted, differ = 0, []
        for size in range(6):
            for chars in itertools.product(alphabet, repeat=size):
                text = "[" + "".join(chars) + "]"
                value = bootstrap._value(text)
                if value is None:
                    continue
                admitted += 1
                try:
                    loaded = yaml.safe_load(f"k: {text}\n")["k"]
                except yaml.YAMLError as exc:
                    loaded = type(exc).__name__
                if loaded != bootstrap._flow_items(value):
                    differ.append((text, loaded))
        self.assertEqual(differ, [])
        self.assertGreater(admitted, 100)

    def test_a_workflow_with_a_lone_dash_event_is_refused_with_its_line(self):
        text = "name: test\non: [- , workflow_call]\njobs: {}\n"
        self.assertIs(bootstrap._declared_inputs(text), bootstrap._UNVERIFIABLE)
        self.assertEqual(bootstrap._scan_rows(text), (None, 2))


if __name__ == "__main__":
    unittest.main()
