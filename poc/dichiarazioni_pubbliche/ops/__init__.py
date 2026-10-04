"""Pure, zero-I/O operational policy modules for the Dichiarazioni Pubbliche M5 lane.

Every module in this package is deterministic, side-effect free, and
unit-testable without a database, a network, or a filesystem write. Modules
here encode *policy*; the daemons and scripts elsewhere in the runtime are
responsible for performing I/O against the policy.
"""
