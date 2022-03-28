"""
test_misc.py ~ Testing of Misc. Functions

Designed for those simple functions that don't need their own dedicated test files
But we want to hit them anyways
"""
from pydle.protocol import identifierify


async def test_identifierify():
    good_name = identifierify("MyVerySimpleName")
    bad_name = identifierify("I'mASpec!äl/Name!_")
    assert good_name == "myverysimplename"
    assert bad_name == "i_maspec__l_name__"
