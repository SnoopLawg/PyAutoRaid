from setuptools import setup,find_packages

setup(
    name='PyAutoRaid',
    description='Automate Raid: Shadow Legends',
    author='Snoop',
    version='0.1.0',
    packages=find_packages(include=['PyAutoRaid','PyAutoRaid.*'])
    
)