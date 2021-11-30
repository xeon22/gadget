# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from setuptools_scm import get_version
from os import path
# io.open is needed for projects that support Python 2.7
# It ensures open() defaults to text mode with universal newlines,
# and accepts an argument to specify the text encoding
# Python 3 only projects can skip this import
from io import open

here = path.abspath(path.dirname(__file__))
my_version = get_version()

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    author='Capco',
    author_email='markpimentel22@gmail.com',
    name='gadget',
    version=my_version,

    use_scm_version={
        'write_to': 'gadget/version.txt',
        'tag_regex': r'^(?P<prefix>v)?(?P<version>[^\+]+)(?P<suffix>.*)?$',
    },

    packages=['gadget', 'gadget/tasks'],

    package_data={
        'gadget': ['version.txt'],
    },

    url='https://bitbucket.org/capcosaas/pz-gadget.git',

    # Classifiers help users find your project by categorizing it.
    #
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish
        # 'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
    ],

    install_requires=[],

    setup_requires=['setuptools_scm'],

    extras_require={  # Optional
        'dev': ['pyinstaller', 'twine', 'setuptools_scm'],
        'test': ['coverage'],
    },

    entry_points={
        'console_scripts': ['gadget = gadget.main:program.run']
    },

)
