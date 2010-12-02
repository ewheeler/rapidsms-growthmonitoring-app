from setuptools import setup, find_packages

setup(
    name='growthmonitoring',
    version='0.1',
    license="BSD",

    install_requires=['rapidsms'],

    description='Growth monitoring application for RapidSMS',

    author='Evan Wheeler, Tobias McNulty',
    author_email='rapidsms@googlegroups.com',

    url='https://github.com/mwana/rapidsms-growthmonitoring-app',
    download_url='https://github.com/mwana/rapidsms-growthmonitoring-app/downloads',

    package_dir={'': 'lib'},
    packages=find_packages('lib', exclude=['*.pyc']),
    include_package_data=True,

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ]
)
