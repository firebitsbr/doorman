# -*- coding: utf-8 -*-
import datetime as dt

from doorman.models import Rule
from doorman.rules import (
    BaseRule,
    BlacklistRule,
    CountRule,
    RuleMatch,
    WhitelistRule,
)


class TestBaseRule:

    def test_will_filter_node_name(self, FakeBaseRule):
        rule = FakeBaseRule(config={'node_name': 'yes'})

        # This should not succeed due to a host_identifier that does not match
        rule.handle_log_entry({}, {'host_identifier': 'no'})
        assert len(rule.calls) == 0

        # This should succeed since the host_identifier does match.  Note that
        # we explicitly don't care about the hostIdentifier value in the query
        # results.
        now = dt.datetime.utcnow()
        rule.handle_log_entry({
            'data': [
                {
                    "diffResults": {
                        "added": [{'op': 'added'}],
                        "removed": "",
                    },
                    "name": "fake",
                    "hostIdentifier": "hostname.local",
                    "calendarTime": "%s %s" % (now.ctime(), "UTC"),
                    "unixTime": now.strftime('%s')
                }
            ]
        }, {'host_identifier': 'yes'})
        assert len(rule.calls) == 1


class TestEachResultRule:
    def setup_method(self, _method):
        self.now = dt.datetime.utcnow()
        self.fake_data = {
            'data': [
                {
                    "diffResults": {
                        "added": [{'op': 'added'}],
                        "removed": [{'op': 'removed'}],
                    },
                    "name": "fake",
                    "hostIdentifier": "hostname.local",
                    "calendarTime": "%s %s" % (self.now.ctime(), "UTC"),
                    "unixTime": self.now.strftime('%s')
                },
            ],
        }

    def test_will_filter_action_added(self, FakeEachResultRule):
        node = {'host_identifier': 'hostname.local'}
        rule = FakeEachResultRule(action=Rule.ADDED, config={})
        rule.handle_log_entry(self.fake_data, node)

        assert rule.calls == [(Rule.ADDED, {'op': 'added'}, node)]

    def test_will_filter_action_removed(self, FakeEachResultRule):
        node = {'host_identifier': 'hostname.local'}
        rule = FakeEachResultRule(action=Rule.REMOVED, config={})
        rule.handle_log_entry(self.fake_data, node)

        assert rule.calls == [(Rule.REMOVED, {'op': 'removed'}, node)]

    def test_will_filter_action_both(self, FakeEachResultRule):
        node = {'host_identifier': 'hostname.local'}
        rule = FakeEachResultRule(action=Rule.BOTH, config={})
        rule.handle_log_entry(self.fake_data, node)

        assert rule.calls == [
            (Rule.ADDED, {'op': 'added'}, node),
            (Rule.REMOVED, {'op': 'removed'}, node),
        ]

    def test_will_filter_query_name(self, FakeEachResultRule):
        self.fake_data['data'].append({
            "diffResults": {
                "added": [{'op': 'added 2'}],
                "removed": [{'op': 'removed 2'}],
            },
            "name": "other",
            "hostIdentifier": "hostname.local",
            "calendarTime": "%s %s" % (self.now.ctime(), "UTC"),
            "unixTime": self.now.strftime('%s')
        })

        node = {'host_identifier': 'hostname.local'}

        # No filtering
        rule = FakeEachResultRule(action=Rule.BOTH, config={})
        rule.handle_log_entry(self.fake_data, node)

        assert rule.calls == [
            (Rule.ADDED, {'op': 'added'}, node),
            (Rule.REMOVED, {'op': 'removed'}, node),
            (Rule.ADDED, {'op': 'added 2'}, node),
            (Rule.REMOVED, {'op': 'removed 2'}, node),
        ]

        rule = FakeEachResultRule(action=Rule.BOTH, config={'query_name': 'other'})
        rule.handle_log_entry(self.fake_data, node)
        assert rule.calls == [
            (Rule.ADDED, {'op': 'added 2'}, node),
            (Rule.REMOVED, {'op': 'removed 2'}, node),
        ]


class TestBlacklistRule:

    def test_will_blacklist(self):
        now = dt.datetime.utcnow()

        data = [
            {
              "diffResults": {
                "added": [
                  {
                    "name": "malware",
                    "path": "/usr/local/bin/malware",
                    "pid": "12345"
                  },
                  {
                    "name": "legit",
                    "path": "/usr/local/bin/legit",
                    "pid": "6789"
                  },
                  {
                    "name": "malware",
                    "path": "/usr/local/bin/malware",
                    "pid": "10000"
                  },
                ],
                "removed": "",
              },
              "name": "processes",
              "hostIdentifier": "hostname.local",
              "calendarTime": "%s %s" % (now.ctime(), "UTC"),
              "unixTime": now.strftime('%s'),
            },
        ]
        node = {'host_identifier': 'hostname.local'}

        rule = BlacklistRule(0, Rule.BOTH, config={
            'field_name': 'name',
            'blacklist': ['malware'],
        })

        expected1 = RuleMatch(
            rule_id=0,
            action='added',
            node=node,
            match=data[0]['diffResults']['added'][0],
        )
        expected2 = RuleMatch(
            rule_id=0,
            action='added',
            node=node,
            match=data[0]['diffResults']['added'][2],
        )

        # Blacklists the two matching things, but not the middle one.
        matches = rule.handle_log_entry({'data': data}, node)
        assert matches == [expected1, expected2]


class TestWhitelistRule:

    def test_will_whitelist(self):
        now = dt.datetime.utcnow()

        data = [
            {
              "diffResults": {
                "added": [
                  {
                    "name": "good",
                    "path": "/usr/local/bin/good",
                    "pid": "12345"
                  },
                  {
                    "name": "unknown",
                    "path": "/usr/local/bin/unknown",
                    "pid": "6789"
                  },
                  {
                    "name": "othergood",
                    "path": "/usr/local/bin/othergood",
                    "pid": "10000"
                  },
                ],
                "removed": "",
              },
              "name": "processes",
              "hostIdentifier": "hostname.local",
              "calendarTime": "%s %s" % (now.ctime(), "UTC"),
              "unixTime": now.strftime('%s'),
            },
        ]
        node = {'host_identifier': 'hostname.local'}

        rule = WhitelistRule(0, Rule.BOTH, config={
            'field_name': 'name',
            'whitelist': ['good', 'othergood'],
        })

        expected = RuleMatch(
            rule_id=0,
            action='added',
            node=node,
            match=data[0]['diffResults']['added'][1],
        )

        # Whitelists the two matching things, but not the middle one.
        matches = rule.handle_log_entry({'data': data}, node)
        assert matches == [expected]

    def test_ignore_nulls(self):
        now = dt.datetime.utcnow()

        data = [
            {
              "diffResults": {
                "added": [
                  {
                    "name": None,
                    "path": "/usr/local/bin/good",
                    "pid": "12345"
                  },
                ],
                "removed": "",
              },
              "name": "processes",
              "hostIdentifier": "hostname.local",
              "calendarTime": "%s %s" % (now.ctime(), "UTC"),
              "unixTime": now.strftime('%s'),
            },
        ]
        node = {'host_identifier': 'hostname.local'}

        rule1 = WhitelistRule(0, Rule.BOTH, config={
            'field_name': 'name',
            'whitelist': ['good'],
            'ignore_null': False,
        })
        rule2 = WhitelistRule(1, Rule.BOTH, config={
            'field_name': 'name',
            'whitelist': ['good'],
            'ignore_null': True,
        })

        expected = RuleMatch(
            rule_id=0,
            action='added',
            node=node,
            match=data[0]['diffResults']['added'][0],
        )

        assert rule1.handle_log_entry({'data': data}, node) == [expected]
        assert rule2.handle_log_entry({'data': data}, node) == []


class TestCountRule:

    def setup_method(self, _method):
        self.now = dt.datetime.utcnow()

    def test_basic_counting(self):
        node = {'host_identifier': 'hostname.local'}
        log = {
            'data': [
                {
                    "diffResults": {
                        "added": [{'op': 'one'}, {'op': 'two'}, {'op': 'three'}],
                        "removed": [],
                    },
                    "name": "fake",
                    "hostIdentifier": "hostname.local",
                    "calendarTime": "%s %s" % (self.now.ctime(), "UTC"),
                    "unixTime": self.now.strftime('%s')
                },
            ],
        }

        def run_rule(count, direction, id=0, action=Rule.BOTH):
            rule = CountRule(id, action, config={'count': count, 'direction': direction})
            return rule.handle_log_entry(log, node)

        # Equal works
        assert run_rule(3, 'equal') == [RuleMatch(0, node, None, 3)]

        # Greater works
        assert run_rule(2, 'greater') == [RuleMatch(0, node, None, 3)]

        # Greater has no false positives
        assert run_rule(3, 'greater') == []

        # Less works
        assert run_rule(4, 'less') == [RuleMatch(0, node, None, 3)]

        # Less has no false positives
        assert run_rule(3, 'less') == []

    def test_query_name_filtering(self):
        node = {'host_identifier': 'hostname.local'}
        log = {
            'data': [
                {
                    "diffResults": {
                        "added": [{'foo': 'one'}],
                        "removed": [{'foo': 'two'}],
                    },
                    "name": "query-1",
                    "hostIdentifier": "hostname.local",
                    "calendarTime": "%s %s" % (self.now.ctime(), "UTC"),
                    "unixTime": self.now.strftime('%s')
                },
                {
                    "diffResults": {
                        "added": [{'foo': 'three'}, {'foo': 'four'}],
                        "removed": [{'foo': 'five'}, {'foo': 'six'}],
                    },
                    "name": "query-2",
                    "hostIdentifier": "hostname.local",
                    "calendarTime": "%s %s" % (self.now.ctime(), "UTC"),
                    "unixTime": self.now.strftime('%s')
                },
            ],
        }

        # This 'equal' rule will only match if we're considering just the first event.
        rule = CountRule(0, Rule.BOTH, config={
            'count': 2,
            'direction': 'equal',
            'query_name': 'query-1',
        })
        matches = rule.handle_log_entry(log, node)
        assert matches == [RuleMatch(0, node, None, 2)]

        # This 'equal' rule will only match if we're considering just the second event.
        rule = CountRule(0, Rule.BOTH, config={
            'count': 4,
            'direction': 'equal',
            'query_name': 'query-2',
        })
        matches = rule.handle_log_entry(log, node)
        assert matches == [RuleMatch(0, node, None, 4)]

    def test_action_filtering(self):
        node = {'host_identifier': 'hostname.local'}
        log = {
            'data': [
                {
                    "diffResults": {
                        "added": [{'foo': 'one'}],
                        "removed": [{'foo': 'two'}, {'foo': 'three'}],
                    },
                    "name": "fake",
                    "hostIdentifier": "hostname.local",
                    "calendarTime": "%s %s" % (self.now.ctime(), "UTC"),
                    "unixTime": self.now.strftime('%s')
                },
            ],
        }

        # This 'equal' rule will only match if we're considering just 'added' columns
        rule = CountRule(0, Rule.ADDED, config={
            'count': 1,
            'direction': 'equal',
        })
        matches = rule.handle_log_entry(log, node)
        assert matches == [RuleMatch(0, node, None, 1)]

        # This 'equal' rule will only match if we're considering just 'removed' columns
        rule = CountRule(0, Rule.REMOVED, config={
            'count': 2,
            'direction': 'equal',
        })
        matches = rule.handle_log_entry(log, node)
        assert matches == [RuleMatch(0, node, None, 2)]
