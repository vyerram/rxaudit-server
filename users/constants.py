from enum import Enum


class AccessControlTypeCodes(Enum):
    Entity = "ENT"
    Attribute = "ATB"
    Custom = "CTM"


class UserRoleCodes(Enum):
    SuperUser = "SU"
    PharmacyUser = "PU"
    VolumeUser = "VG"


class AccessType(Enum):
    FULL = "FULL"
    READ = "READ"
    ENCRYPT = "ECPT"
    LAST3 = "L3"


user_signup_template = """Hi, Welcome to All-Win Rx!

You're now part of a growing community. To complete sign up process, click the below link and discover the exciting features waiting for you. 

Sign up now: %s
Username: %s
Password: %s

If you have any questions, our support team is here to help:  info@allwinrx.com/+1(973) 444-5080.

Best regards,
All-Win Rx"""
