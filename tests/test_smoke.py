import unittest


class SmokeTest(unittest.TestCase):
    def test_import(self):
        import deckscan  # noqa: F401


if __name__ == "__main__":
    unittest.main()
