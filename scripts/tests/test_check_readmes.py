import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_readmes as check


class PersonalContactQrGuardTests(unittest.TestCase):
    def test_detects_personal_contact_qr_filenames(self):
        for name in (
            "qq_qr.jpg",
            "feishu_qr.jpg",
            "wechat-qr.png",
            "weixin_qrcode.webp",
            "contact_qr.jpeg",
        ):
            self.assertTrue(check.is_personal_contact_qr_name(name), name)
            self.assertTrue(check.is_personal_contact_qr_ref(f".github/{name}"), name)

    def test_ignores_product_and_research_assets(self):
        for name in (
            "figA-contact-sheet-r1.jpg",
            "qrcode.svg",
            "WechatOutlined.js",
            "favicon.png",
            "infistar-logo.svg",
        ):
            self.assertFalse(check.is_personal_contact_qr_name(name), name)

    def test_repo_has_no_personal_contact_qr_images(self):
        self.assertEqual(check.iter_personal_contact_qr_files(check.ROOT), [])


if __name__ == "__main__":
    unittest.main()
