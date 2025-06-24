from enum import Enum


class TableTypes(Enum):
    ArchiveTable = "ARC"
    AuditTable = "AUD"
    BaseTable = "BAS"
    LookupTable = "LKP"
    RelationshipTable = "REL"
    SetupTable = "SET"
    TempTable = "TEMP"
    ConfigTable = "CFG"
    OperationalTable = "OPT "


only_alphabets_regular_expression = "[^A-Za-z0-9]+"
