"""Tests for exact parsing semantics, error handling and safe updates."""
import json
import tempfile
import unittest
from pathlib import Path

from convert import build, guard_count, parse_dnsmasq, render, valid_domain


class ParseTests(unittest.TestCase):
    def test_conversion_is_suffix_not_exact(self):
        domains, info = parse_dnsmasq(
            b"# comment\nserver=/Example.COM/114.114.114.114\n"
            b"server=/foo.example.com/bar.cn/223.5.5.5\n"
            b"server=/example.com/114.114.114.114\n", "china")
        self.assertEqual(domains, [".bar.cn", ".example.com", ".foo.example.com"])
        self.assertEqual(info["source_rule_count"], 3)
        self.assertEqual(render(domains), b".bar.cn\n.example.com\n.foo.example.com\n")

    def test_valid_idn_and_cn_tld(self):
        self.assertTrue(valid_domain("xn--fiqs8s"))
        self.assertTrue(valid_domain("cn"))
        self.assertTrue(valid_domain("0.xn--czrs0t"))

    def test_invalid_domains(self):
        for name in ("-bad.com", "bad-.com", "bad..com", "x" * 64 + ".com", "*.cn",
                     "bad_name.com", "example.com.", "8.8.8.8", "中文.cn", ""):
            with self.subTest(name=name):
                self.assertFalse(valid_domain(name))

    def test_non_dnsmasq_or_bad_input_rejected(self):
        for text in (b"", b"<html>oops</html>", b"not a rule", b"server=/a.com/",
                     b"server=//8.8.8.8", b"server=/a.com/not-an-ip", b"server=/a.com/8.8.8.8\nDOMAIN-SUFFIX,b.com"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_dnsmasq(text, "china")


class BuildTests(unittest.TestCase):
    CHINA = b"server=/example.com/114.114.114.114\n"
    APPLE = b"server=/apple.com/114.114.114.114\n"
    MINIMUMS = {"china": 1, "apple-china": 1}

    def test_build_deterministic_no_rewrites(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            inputs = {"china": self.CHINA, "apple-china": self.APPLE}
            report = build(inputs, out, self.MINIMUMS)
            self.assertEqual((out / "china.txt").read_text(), ".example.com\n")
            self.assertEqual((out / "apple-china.txt").read_text(), ".apple.com\n")
            self.assertEqual(json.loads((out / "report.json").read_text()), report)
            self.assertEqual(build(inputs, out, self.MINIMUMS), report)

    def test_partial_failure_preserves_prior_files(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root)
            build({"china": self.CHINA, "apple-china": self.APPLE}, out, self.MINIMUMS)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(ValueError):
                build({"china": b"server=/changed.com/8.8.8.8\n", "apple-china": b"<bad>"}, out, self.MINIMUMS)
            self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_shrink_guard(self):
        with self.assertRaisesRegex(ValueError, "dropped"):
            guard_count("china", 10, 1, 100, .20, .50)
        with self.assertRaisesRegex(ValueError, "grew"):
            guard_count("china", 200, 1, 100, .20, .50)

    def test_both_sources_required(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                build({"china": self.CHINA}, Path(root), self.MINIMUMS)


if __name__ == "__main__":
    unittest.main()
