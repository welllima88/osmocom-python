#!/usr/bin/env python

# (C) 2013 by Katerina Barone-Adesi <kat.obsc@gmail.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import os.path
import time
import sys
import tempfile

import osmopy.obscvty as obscvty
import osmopy.osmoutil as osmoutil


# Return true iff all the tests for the given config pass
def test_config(app_desc, config, tmpdir, verbose=True):
    try:
        test_config_atest(app_desc, config, verify_doc, verbose)

        newconfig = copy_config(tmpdir, config)
        test_config_atest(app_desc, newconfig, write_config, verbose)
        test_config_atest(app_desc, newconfig, token_vty_command, verbose)
        return 0

    # If there's a socket error, skip the rest of the tests for this config
    except IOError:
        return 1


def test_config_atest(app_desc, config, run_test, verbose=True):
    proc = None
    ret = None
    try:
        cmd = [app_desc[1], "-c", config]
        if verbose:
            print "Verifying %s, test %s" % (' '.join(cmd), run_test.__name__)

        proc = osmoutil.popen_devnull(cmd)
        time.sleep(1)
        end = app_desc[2]
        port = app_desc[0]
        vty = obscvty.VTYInteract(end, "127.0.0.1", port)
        ret = run_test(vty)

    except IOError as se:
        print >> sys.stderr, "Failed to verify %s" % ' '.join(cmd)
        print >> sys.stderr, "Error was %s" % se
        raise se

    finally:
        if proc:
            osmoutil.end_proc(proc)

    return ret


def copy_config(dirname, config):
    try:
        os.stat(dirname)
    except OSError:
        os.mkdir(dirname)
    else:
        remove_tmpdir(dirname)
        os.mkdir(dirname)

    prefix = os.path.basename(config)
    tmpfile = tempfile.NamedTemporaryFile(
        dir=dirname, prefix=prefix, delete=False)
    tmpfile.write(open(config).read())
    tmpfile.close()
    # This works around the precautions NamedTemporaryFile is made for...
    return tmpfile.name


def write_config(vty):
    new_config = vty.enabled_command("write")
    return new_config.split(' ')[-1]


# The only purpose of this function is to verify a working vty
def token_vty_command(vty):
    vty.command("help")
    return True


# This may warn about the same doc missing multiple times, by design
def verify_doc(vty):
    xml = vty.command("show online-help")
    split_at = "<command"
    all_errs = []
    for command in xml.split(split_at):
        if "(null)" in command:
            lines = command.split("\n")
            cmd_line = split_at + lines[0]
            err_lines = []
            for line in lines:
                if '(null)' in line:
                    err_lines.append(line)

            all_errs.append(err_lines)

            print >> sys.stderr, \
                "Documentation error (missing docs): \n%s\n%s\n" % (
                cmd_line, '\n'.join(err_lines))

    return (len(all_errs), all_errs)


# Skip testing the configurations of anything that hasn't been compiled
def app_exists(app_desc):
    cmd = app_desc[1]
    return os.path.exists(cmd)


def remove_tmpdir(tmpdir):
    files = os.listdir(tmpdir)
    for f in files:
        os.unlink(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)


def check_configs_tested(basedir, app_configs):
    configs = []
    for root, dirs, files in os.walk(basedir):
        for f in files:
            if f.endswith(".cfg"):
                configs.append(os.path.join(root, f))
    for config in configs:
        found = False
        for app in app_configs:
            if config in app_configs[app]:
                found = True
        if not found:
            print >> sys.stderr, "Warning: %s is not being tested" % config


def test_all_apps(apps, app_configs, tmpdir="writtenconfig", verbose=True,
                  rmtmp=False):
    check_configs_tested("doc/examples/", app_configs)
    errors = 0
    for app in apps:
        if not app_exists(app):
            print >> sys.stderr, "Skipping app %s (not found)" % app[1]
            continue

        configs = app_configs[app[3]]
        for config in configs:
            errors |= test_config(app, config, tmpdir, verbose)

    if rmtmp:
        remove_tmpdir(tmpdir)

    return errors


if __name__ == '__main__':
    import argparse

    confpath = "."

    parser = argparse.ArgumentParser()
    parser.add_argument("--e1nitb", action="store_true", dest="e1nitb")
    parser.add_argument("-v", "--verbose", dest="verbose",
                        action="store_true", help="verbose mode")
    parser.add_argument("-p", "--pythonconfpath", dest="p",
                        help="searchpath for config")
    args = parser.parse_args()

    if args.p:
        confpath = args.p

    osmoappdesc = None
    try:
        osmoappdesc = osmoutil.importappconf(confpath, "osmoappdesc")
    except ImportError as e:
        print >> sys.stderr, "osmoappdesc not found, set searchpath with -p"
        sys.exit(1)

    apps = osmoappdesc.apps
    configs = osmoappdesc.app_configs

    if args.e1nitb:
        configs['nitb'].extend(osmoappdesc.nitb_e1_configs)

    sys.exit(test_all_apps(apps, configs, verbose=args.verbose))
