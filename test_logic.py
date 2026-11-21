import unittest
from finance import fee_split

class FeeSplitTests(unittest.TestCase):
    def test_hundred_rupee_order(self):
        self.assertEqual(fee_split(100), {
            'gross':100.0,'platform_fee':1.0,'maintenance_fee':1.0,
            'owner_fee':3.0,'total_fee':5.0,'seller_net':95.0
        })
    def test_zero_and_negative_not_used(self):
        self.assertEqual(fee_split(0)['seller_net'],0.0)
    def test_decimal_amount(self):
        split=fee_split(250.50)
        self.assertEqual(split['total_fee'],12.54)
        self.assertEqual(split['seller_net'],237.96)

if __name__=='__main__': unittest.main()
