"""Copy the tracking plan into wheels without maintaining a second registry."""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / 'backend' / 'core' / 'event_catalog.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).parent / 'docs/analytics/event_catalog.json', target)


setup(cmdclass={'build_py': BuildPy})
