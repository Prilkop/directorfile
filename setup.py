from setuptools import find_packages, setup

setup(
    name='directorfile',
    version='0.0.1',
    author='Adam Rimon',
    author_email='',
    description='A python module to read and manipulate Macromedia/Adobe Director files',
    url='https://github.com/Prilkop/directorfile',
    license='MIT License',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',

        'Intended Audience :: Developers',

        'Programming Language :: Python',
        'Topic :: File Formats',
        'Topic :: Utilities',

        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
)
