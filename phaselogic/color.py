import os
import sys

_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""
_STDERR_ENABLED = sys.stderr.isatty() and os.environ.get("NO_COLOR", "") == ""

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _ENABLED else text


def _cs(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _STDERR_ENABLED else text


def cyan_bold(text: str) -> str: return _c(_BOLD + _CYAN, text)
def green(text: str) -> str:     return _c(_GREEN, text)
def red(text: str) -> str:       return _c(_RED, text)
def red_bold(text: str) -> str:  return _c(_BOLD + _RED, text)
def yellow(text: str) -> str:    return _c(_YELLOW, text)

# Stderr variants for components writing to stderr (spinner, live table)
def s_green(text: str) -> str:   return _cs(_GREEN, text)
def s_red(text: str) -> str:     return _cs(_RED, text)
def s_yellow(text: str) -> str:  return _cs(_YELLOW, text)
