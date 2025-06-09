from enum import Enum


class ProcessingStatusCodes(Enum):
    Success = "scs"
    Inprogress = "inp"
    Failure = "fail"
