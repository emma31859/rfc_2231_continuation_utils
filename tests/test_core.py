import unittest

from rfc_2231_continuation_utils import decode_parameter, decode_parameter_dict


class DecodeParameterTests(unittest.TestCase):
    def test_single_encoded_segment(self):
        fragments = {"name*0*": "utf-8'en'%41%42%43"}
        self.assertEqual(decode_parameter("name", fragments), "ABC")

    def test_split_utf8_across_segments(self):
        # The euro sign U+20AC is three UTF-8 bytes e2 82 ac.
        fragments = {
            "name*0*": "utf-8'en'%e2%82",
            "name*1*": "%ac",
        }
        self.assertEqual(decode_parameter("name", fragments), "\u20ac")

    def test_multi_segment_ascii(self):
        fragments = {
            "filename*0*": "utf-8''file",
            "filename*1*": "name.txt",
        }
        self.assertEqual(decode_parameter("filename", fragments), "filename.txt")

    def test_implicit_segment_zero_index(self):
        # "name*" with no numeric index is treated as index 0.
        fragments = {"name*": "utf-8'en'%41%42%43"}
        self.assertEqual(decode_parameter("name", fragments), "ABC")

    def test_continuation_indexes_are_positional_not_lexical(self):
        # Indexes 2 and 10 must be ordered numerically, not as strings.
        fragments = {
            "name*0*": "utf-8'en'%41",
            "name*10*": "%43",
            "name*2*": "%42",
        }
        self.assertEqual(decode_parameter("name", fragments), "ABC")

    def test_unencoded_continuation_used_when_no_encoded_present(self):
        fragments = {
            "name*0": "hello",
            "name*1": " world",
        }
        self.assertEqual(decode_parameter("name", fragments), "hello world")

    def test_encoded_segments_override_unencoded_dupes(self):
        fragments = {
            "name*0": "RAW",
            "name*0*": "utf-8'en'%41%42%43",
        }
        self.assertEqual(decode_parameter("name", fragments), "ABC")

    def test_missing_parameter_returns_none(self):
        self.assertIsNone(decode_parameter("name", {"other*0*": "utf-8'en'%41"}))

    def test_empty_fragment_dict(self):
        self.assertIsNone(decode_parameter("name", {}))

    def test_case_insensitive_keys(self):
        fragments = {"NAME*0*": "UTF-8'EN'%41%42%43"}
        self.assertEqual(decode_parameter("name", fragments), "ABC")

    def test_unknown_charset_falls_back_to_utf8(self):
        fragments = {"name*0*": "bogus'lang'%41%42"}
        self.assertEqual(decode_parameter("name", fragments), "AB")

    def test_preserves_unencoded_bytes_in_body(self):
        # The charset prefix is parsed off, but literal characters in the body
        # after the second quote are kept verbatim (here "YZ").
        fragments = {"name*0*": "utf-8'en'%41YZ"}
        self.assertEqual(decode_parameter("name", fragments), "AYZ")

    def test_wraps_via_dict_function(self):
        headers = {"Content-Disposition": "attachment",
                   "filename*0*": "utf-8''report.pdf",
                   "filename*1*": "%20final"}
        self.assertEqual(decode_parameter_dict(headers, "filename"),
                         "report.pdf final")


if __name__ == "__main__":
    unittest.main()
