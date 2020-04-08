import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="podmanspawner", # Replace with your own username
    version="0.2.2",
    author="Niklas Netter",
    author_email="niknett@gmail.com",
    description="PodmanSpawner for JupyterHub",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gatoniel/podmanspawner",
    packages=setuptools.find_packages(),
    license="BSD",
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    project_urls={
        'Documentation': 'https://jupyterhub.readthedocs.io',
        'Source': 'https://github.com/gatoniel/podmanspawner',
        'Tracker': 'https://github.com/gatoniel/podmanspawner/issues',
    },
    platofrms="Linux",
    python_requires='>=3.5', # like JupyterHub
    entry_points={
        'jupyterhub.spawners': [
            'podmanspawner = podmanspawner:PodmanSpawner',
        ],
  },
)
