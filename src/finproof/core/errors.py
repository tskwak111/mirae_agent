"""Transport-independent FinProof errors."""


class FinProofError(Exception):
    """Base FinProof application error."""


class SourceContractError(FinProofError):
    """Official source data violated a frozen contract."""
