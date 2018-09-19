# -*- coding: utf-8 -*-
# Copyright (c) The python-semanticversion project
# This code is distributed under the two-clause BSD License.

from __future__ import unicode_literals
import datetime
import re
import time
from distutils.version import Version

'''
This model is used to compare versions and is defined in strict mode with release date property for ease of use
a version consists of major, minor, patch, pre_release, release_date

major, minor, patch must be int
release_date must be in format '2017/01/21'
pre_release should be weighted against keyword list

valid versions:
1.0
5.3-alpha
5.3-alpha.1
2.1.12
2.1.12-beta1021
4.4_build_4.4.000
11.6.5.1.1-20161213


invalid versions:
5.4h.1
3alpha
8231-e2c
v100r002c00spc108

for pre_release:
"alpha" < "beta" < "milestone" < "rc" = "cr" < "snapshot" < "" = "final" = "ga" < "sp"

'''


class SemanticVersion(Version):
    # "alpha" = "a" < "beta" = "b" < "milestone" < "rc" = "cr" < "snapshot" < "" = "final" = "ga" < "sp"
    pre_release_weight = {"alpha": 1,
                          "a": 1,
                          "beta": 2,
                          "b": 2,
                          "milestone": 3,
                          "m": 3,
                          "rc": 4,
                          "cr": 4,
                          "": 6,
                          "final": 7,
                          "ga": 8,
                          "sp": 9}

    def __init__(self, vstring=None, release_date=None, pre_release_weight=None):
        if pre_release_weight:
            self.pre_release_weight = pre_release_weight
        if vstring:
            self.parse(vstring, release_date)

    def parse(self, version_string, release_date=None):
        if not version_string:
            raise ValueError(f"{version_string}: version_string is empty.")

        v_vectors = version_string.split('.')
        v_cnt = len(v_vectors)
        if v_cnt == 1:
            raise ValueError(f"{version_string}: version_string is invalid.")

        major = v_vectors[0]
        if not re.match(r'^\d+$', major):
            raise ValueError(f"{version_string}: major version is invalid.")

        patch = 0
        pre_release = ""

        raw_minor = v_vectors[1]
        if re.match(r'^\d+$', raw_minor):
            minor = raw_minor
        elif re.match(r'^\d+([-_]).*$', raw_minor):
            raw_minor = '.'.join(v_vectors[1:])
            index = re.search(r'[-_]', raw_minor).start()
            minor = raw_minor[:index]
            pre_release = raw_minor[index + 1:]
            # if minor has pre release info, don look for patch
            v_cnt = 2
        else:
            raise ValueError(f"{version_string}: minor version is invalid.")

        if v_cnt > 2:
            raw_patch = v_vectors[2]
            if re.match(r'^\d+$', raw_patch):
                patch = raw_patch
                pre_release = '.'.join(v_vectors[3:])
            else:
                raw_patch = '.'.join(v_vectors[2:])
                index = re.search(r'[-_]', raw_patch).start()
                patch = raw_patch[:index]
                pre_release = raw_patch[index + 1:]

        try:
            self.major = int(major)
            self.minor = int(minor)
            self.patch = int(patch) if not patch else ''
        except ValueError:
            raise ValueError(f"{version_string}: major, minor or patch is invalid.")

        # convert to weight according to priority
        pre_release_weight_key = ""
        for key in list(self.pre_release_weight.keys()):
            if pre_release.__contains__(key):
                pre_release_weight_key = key
                break
        self.pre_release = pre_release
        pre_release_num = self.pre_release_weight.get(pre_release_weight_key)
        self.pre_release_num = pre_release_num

        try:
            release_date = time.mktime(
                datetime.datetime.strptime(release_date, "%Y/%m/%d").timetuple()) if release_date else None
        except ValueError:
            raise ValueError(f"{version_string}: release_date is invalid.")
        self.release_date = release_date
        self.version = tuple(map(int, [major, minor, patch, pre_release_num]))
        self.version_string = version_string

    def __str__(self):
        release_date = str(self.release_date) if self.release_date else 'N.A.'
        return self.version_string + ':' + release_date

    def _cmp(self, other):
        if not isinstance(other, SemanticVersion):
            raise ValueError(f'{other} is not a valid SemanticVersion.')

        # if release date is present, use release date
        if self.release_date and other.release_date:
            if self.release_date == other.release_date:
                return 0
            elif self.release_date < other.release_date:
                return -1
            else:
                return 1

        # compare main version number
        if self.version != other.version:
            if self.version < other.version:
                return -1
            else:
                return 1

        # compare pre release weight
        if self.pre_release_num != other.pre_release_num:
            if self.pre_release_num < other.pre_release_num:
                return -1
            else:
                return 1
        else:
            if self.pre_release == other.pre_release:
                return 0
            elif self.pre_release < other.pre_release:
                return -1
            else:
                return 1


class SpecItem(object):
    """A requirement specification."""

    KIND_ANY = '*'
    KIND_LT = '<'
    KIND_LTE = '<='
    KIND_EQUAL = '=='
    KIND_SHORTEQ = '='
    KIND_EMPTY = ''
    KIND_GTE = '>='
    KIND_GT = '>'
    KIND_NEQ = '!='
    KIND_CARET = '^'
    KIND_TILDE = '~'
    KIND_COMPATIBLE = '~='

    # Map a kind alias to its full version
    KIND_ALIASES = {
        KIND_SHORTEQ: KIND_EQUAL,
        KIND_EMPTY: KIND_EQUAL,
    }

    re_spec = re.compile(r'^(<|<=||=|==|>=|>|!=|\^|~|~=)(\d.*)$')

    def __init__(self, requirement_string):
        kind, spec = self.parse(requirement_string)
        self.kind = kind
        self.spec = spec

    @classmethod
    def parse(cls, requirement_string):
        if not requirement_string:
            raise ValueError(
                "Invalid empty requirement specification: %r" % requirement_string)

        # Special case: the 'any' version spec.
        if requirement_string == '*':
            return (cls.KIND_ANY, '')

        match = cls.re_spec.match(requirement_string)
        if not match:
            raise ValueError(
                "Invalid requirement specification: %r" % requirement_string)

        kind, version = match.groups()
        if kind in cls.KIND_ALIASES:
            kind = cls.KIND_ALIASES[kind]

        spec = SemanticVersion(version)
        return (kind, spec)

    def match(self, version):
        if self.kind == self.KIND_ANY:
            return True
        elif self.kind == self.KIND_LT:
            return version < self.spec
        elif self.kind == self.KIND_LTE:
            return version <= self.spec
        elif self.kind == self.KIND_EQUAL:
            return version == self.spec
        elif self.kind == self.KIND_GTE:
            return version >= self.spec
        elif self.kind == self.KIND_GT:
            return version > self.spec
        elif self.kind == self.KIND_NEQ:
            return version != self.spec
        elif self.kind == self.KIND_CARET:
            if self.spec.major != 0:
                upper = self.spec.next_major()
            elif self.spec.minor != 0:
                upper = self.spec.next_minor()
            else:
                upper = self.spec.next_patch()
            return self.spec <= version < upper
        elif self.kind == self.KIND_TILDE:
            return self.spec <= version < self.spec.next_minor()
        elif self.kind == self.KIND_COMPATIBLE:
            if self.spec.patch is not None:
                upper = self.spec.next_minor()
            else:
                upper = self.spec.next_major()
            return self.spec <= version < upper
        else:  # pragma: no cover
            raise ValueError('Unexpected match kind: %r' % self.kind)

    def __str__(self):
        return '%s%s' % (self.kind, self.spec)

    def __repr__(self):
        return '<SpecItem: %s %r>' % (self.kind, self.spec)

    def __eq__(self, other):
        if not isinstance(other, SpecItem):
            return NotImplemented
        return self.kind == other.kind and self.spec == other.spec

    def __hash__(self):
        return hash((self.kind, self.spec))


class Spec(object):
    def __init__(self, *specs_strings):
        subspecs = [self.parse(spec) for spec in specs_strings]
        self.specs = sum(subspecs, ())

    @classmethod
    def parse(self, specs_string):
        spec_texts = specs_string.split(',')
        return tuple(SpecItem(spec_text) for spec_text in spec_texts)

    def match(self, version):
        """Check whether a Version satisfies the Spec."""
        return all(spec.match(version) for spec in self.specs)

    def filter(self, versions):
        """Filter an iterable of versions satisfying the Spec."""
        for version in versions:
            if self.match(version):
                yield version

    def select(self, versions):
        """Select the best compatible version among an iterable of options."""
        options = list(self.filter(versions))
        if options:
            return max(options)
        return None

    def __contains__(self, version):
        if isinstance(version, SemanticVersion):
            return self.match(version)
        return False

    def __iter__(self):
        return iter(self.specs)

    def __str__(self):
        return ','.join(str(spec) for spec in self.specs)

    def __repr__(self):
        return '<Spec: %r>' % (self.specs,)

    def __eq__(self, other):
        if not isinstance(other, Spec):
            return NotImplemented

        return set(self.specs) == set(other.specs)

    def __hash__(self):
        return hash(self.specs)


def compare(v1, v2):
    return base_cmp(SemanticVersion(v1), SemanticVersion(v2))


def match(spec, version):
    return Spec(spec).match(SemanticVersion(version))


def validate(version_string):
    """Validates a version string againt the SemVer specification."""
    try:
        SemanticVersion.parse(version_string)
        return True
    except ValueError:
        return False


def base_cmp(x, y):
    if x == y:
        return 0
    elif x > y:
        return 1
    elif x < y:
        return -1
    else:
        # Fix Py2's behavior: cmp(x, y) returns -1 for unorderable types
        return NotImplemented


def check_version_in_criteria(criterias, version):
    ret = False

    for spec in criterias:
        ret = ret or spec.match(version)
        if len(spec.specs) == 2:
            for spec_item in spec.specs:
                if spec_item.spec.major == version.major and spec_item.spec.minor == version.minor:
                    ret = spec.match(version)
                    break
    return ret
