"""
All the exceptions for backstage go here !!
"""

class Raise404Exception(Exception):
    pass

class Raise405Exception(Exception):
    pass

class Raise429Exception(Exception):
    pass

class Raise401Exception(Exception):
    pass

class InvalidGrantTypeException(Exception):
    pass

class RunOutSequence(Exception):
    pass

class RunNamedSequence(Exception):
    pass

class InvalidGrantTypeException(Exception):
    pass

class TokenRevocationException(Exception):
    pass

class IncorrectAuthorizationCodeException(Exception):
    pass
