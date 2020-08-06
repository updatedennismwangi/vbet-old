import setuptools
import vbet

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="vbet",
    version=vbet.__VERSION__,
    author="Dennis Mwangi",
    author_email="updatedennismwangi@gmail.com",
    description="A virtual betting bot server",
    long_description=long_description,
    long_description_content_type="text/html",
    url="https://github.com/updatemenow/",
    packages=setuptools.find_packages(),
    scripts=['bin/run', 'bin/vs'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Linux(Debian)",
        "License :: GPL V3 :: GNU GENERAL PUBLIC LICENSE"
    ],
    python_requires='>=3.6',
)
