import unittest
class Tests(unittest.TestCase):
    def test_sum(self): self.assertEqual(sum([1,2,3]),6)
result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
assert result.wasSuccessful()
