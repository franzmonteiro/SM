#!/usr/bin/python

import unittest
import sm

class TestIsAssociationAllowedMethod(unittest.TestCase):

    def setUp(self):
        self.parent_incident = { 'IncidentID': 'IM1234567',
                                 'Severity': 3,
                                 'BriefDescription': 'server service data_center',
                                 'PrimaryAssignmentGroup': '' }
        self.dependent_incident = { 'IncidentID': 'IM7654321',
                                    'Severity': 3,
                                    'BriefDescription': 'server service data_center',
                                    'PrimaryAssignmentGroup': '' }

    def tearDown(self):
        pass

    def test_incident_severity(self):
        self.assertTrue(sm.is_association_allowed(self.parent_incident, self.dependent_incident))

if __name__ == '__main__':
    unittest.main()

