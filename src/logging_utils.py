"""Shared logging utilities with colorful output."""
import logging
import sys


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record):
        # Save original values
        orig_levelname = record.levelname
        orig_name = record.name
        orig_msg = record.msg
        
        # Apply colors
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{self.BOLD}{record.levelname}{self.RESET}"
        record.name = f"\033[34m{record.name}{self.RESET}"  # Blue for logger name
        record.msg = f"{color}{record.msg}{self.RESET}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original values (in case record is reused)
        record.levelname = orig_levelname
        record.name = orig_name
        record.msg = orig_msg
        
        return result


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger with colorful output.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only add handler if logger doesn't have one
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter('%(levelname)s | %(name)s | %(message)s'))
        logger.addHandler(handler)
    
    logger.setLevel(level)
    return logger
