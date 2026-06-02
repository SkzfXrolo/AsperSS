"""Contexto compartido del pack v1.7 — evita re-escanear rutas en 73 módulos."""
import os


class ScanContext:
    __slots__ = ('app', 'minecraft_root', 'appdata', 'userprofile', 'downloads', 'cache')

    def __init__(self, app):
        self.app = app
        self.appdata = os.environ.get('APPDATA', '') or ''
        self.userprofile = os.environ.get('USERPROFILE', '') or ''
        self.downloads = os.path.join(self.userprofile, 'Downloads') if self.userprofile else ''
        self.minecraft_root = self._find_minecraft()
        self.cache = {}

    def _find_minecraft(self):
        for p in (
            os.path.join(self.appdata, '.minecraft'),
            os.path.join(self.appdata, 'Roaming', '.minecraft'),
        ):
            if p and os.path.isdir(p):
                return p
        return ''

    def get(self, key, factory):
        if key not in self.cache:
            self.cache[key] = factory()
        return self.cache[key]
