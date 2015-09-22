import os

import click

from xml.etree import ElementTree as ET

from planemo.io import info, error
from planemo.cli import pass_context
from planemo import options

from galaxy.tools.loader_directory import load_tool_elements_from_path

from galaxy.tools.deps.requirements import parse_requirements_from_xml
from galaxy.util import bunch

from planemo.shed2tap.base import BasePackage, Dependency

def find_tool_dependencis_xml(path, recursive):
    """Iterator function, quick & dirty tree walking."""
    if os.path.isfile(path):
        if os.path.basename(path) == "tool_dependencies.xml":
            yield path
    elif os.path.isdir(path):
        p = os.path.join(path, "tool_dependencies.xml")
        if os.path.isfile(p):
            yield p
        if recursive:
            for f in os.listdir(path):
                p = os.path.join(path, f)
                if os.path.isdir(p):
                    # TODO: yield from
                    for x in find_tool_dependencis_xml(p, recursive):
                        yield x


def run_tool_dep(dependencies_file, env_file_handle):
    """Execute a tool_dependencies.xml and update env.sh file."""
    root = ET.parse(dependencies_file).getroot()
    package_els = root.findall("package")
    
    packages = []
    dependencies = []
    for package_el in package_els:
        install_els = package_el.findall("install")
        assert len(install_els) in (0, 1)
        if len(install_els) == 0:
            repository_el = package_el.find("repository")
            assert repository_el is not None, "no repository in package el for %s" % repo
            dependencies.append(Dependency(None, package_el, repository_el))
        else:
            install_el = install_els[0]
            packages.append(BasePackage(None, package_el, install_el, readme=None))

    if not packages:
        info("No packages in %s" % dependencies_file)
        return
    assert len(packages) == 1, packages
    package = packages[0]
    name = package_el.attrib["name"]
    version = package_el.attrib["version"]

    info("Installing %s version %s" % (name, version))
    os.environ["INSTALL_DIR"] = os.path.abspath(os.curdir)
    for action in package.all_actions:
        for statement in action.to_bash():
            info(statement)
    info('Done')


@click.command('dep_install')
@options.optional_tools_arg(multiple=True)
@options.recursive_shed_option()
##Currently always as if --fail_fast, otherwise: @options.shed_realization_options()
@pass_context
def cli(ctx, paths, recursive=False):
    """Executes a tool_dependencies.xml to install a dependency (**Experimental**)

    Parses the specified``tool_dependencies.xml`` files, and executes them
    directly within the current working directory (reusing the Galaxy Tool
    Shed functionality), and produces a shell script ``env.sh`` defining any
    new/edited environment variables intended to be used via ``source env.sh``
    prior to running any of the dependencies.

    This is experimental, and is initially intended for use within continuous
    integration testing setups like TravisCI to both verify the dependency
    installation receipe works, and to use this to run functional tests.
    """
    with open("env.sh", "w") as env_sh_handle:
        for path in paths:
            #ctx.log("Checking: %r" % path)
            for tool_dep in find_tool_dependencis_xml(path, recursive):
                assert os.path.basename(tool_dep) == "tool_dependencies.xml", tool_dep
                ctx.log('Installing requirements from %s',
                        click.format_filename(tool_dep))
                run_tool_dep(tool_dep, env_sh_handle)
    ctx.log("The End")
