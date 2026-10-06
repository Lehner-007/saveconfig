"""Begrenzte, datierte Protokollierung mit sichtbaren Sitzungstrennern."""
import logging
from logging.handlers import RotatingFileHandler
from . import VERSION
from .languages import Languages
from .settings import Settings


class SessionFormatter(logging.Formatter):
    def format(self,record):
        text=super().format(record)
        if getattr(record,'session_start',False):
            line='='*72
            return '\n'+line+'\n'+text+'\n'+line
        return text


def setup(root):
    logger=logging.getLogger('saveconfig')
    logger.setLevel(logging.INFO)
    logger.propagate=False
    for handler in list(logger.handlers):
        if getattr(handler,'_saveconfig_managed',False):
            logger.removeHandler(handler);handler.close()
    path=root/'.local/state/saveconfig/logs'
    try:
        path.mkdir(parents=True,exist_ok=True)
        handler=RotatingFileHandler(path/'saveconfig.log',maxBytes=1_000_000,backupCount=3,encoding='utf-8')
        handler.setFormatter(SessionFormatter('%(asctime)s %(message)s','%d.%m.%Y %H:%M:%S'))
    except OSError:handler=logging.NullHandler()
    handler._saveconfig_managed=True
    logger.addHandler(handler)
    logger.info(Languages(Settings(root)).text('started').format(version=VERSION),extra={'session_start':True})
    return logger
