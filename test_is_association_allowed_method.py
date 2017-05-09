#!/usr/bin/python

import unittest
import sm

class TestIsAssociationAllowedMethod(unittest.TestCase):

    def setUp(self):
        self.dependent_incident = { 'IncidentID': 'IM7654321',
                                    'Severity': 5,
                                    'BriefDescription': 'server service data_center',
                                    'PrimaryAssignmentGroup': 'pagseguro oper' }
        
        self.source_incident = { 'PrimaryAssignmentGroup': 'hw' }
    
    def tearDown(self):
        pass
        
    def test_severity(self):
        for severity in range(1, 3):
            self.dependent_incident['Severity'] = severity
            self.assertFalse(sm.is_association_allowed(self.dependent_incident, self.source_incident))
            
        for severity in range(3, 6):
            self.dependent_incident['Severity'] = severity
            self.assertTrue(sm.is_association_allowed(self.dependent_incident, self.source_incident))
        
    def test_brief_description(self):
        forbidden_services = ['swap', 'disk_usage']
        for service in forbidden_services:
            self.dependent_incident['BriefDescription'] = 'a6-hundblue1 {0} dc_gt'.format(service)
            self.assertFalse(sm.is_association_allowed(self.dependent_incident, self.source_incident))
            
        other_services = ['pagseguro-mq_ha_rebate_dead_letter_queue',
                          'Active_HTTP_DataFortress_Probe'] #TODO: Include some others allowed services.
        for service in other_services:
            self.dependent_incident['BriefDescription'] = 'a6-hundblue1 {0} dc_gt'.format(service)
            self.assertTrue(sm.is_association_allowed(self.dependent_incident, self.source_incident))
    
    def test_primary_assignment_group(self):
        self.source_incident['PrimaryAssignmentGroup'] = 'pagseguro oper'
        self.dependent_incident['PrimaryAssignmentGroup'] = self.source_incident['PrimaryAssignmentGroup']
        self.assertFalse(sm.is_association_allowed(self.dependent_incident, self.source_incident))
        
        self.source_incident['PrimaryAssignmentGroup'] = 'hw'
        self.assertTrue(sm.is_association_allowed(self.dependent_incident, self.source_incident))
        
    def test_im_ticket_status(self):
        self.dependent_incident['IMTicketStatus'] = 'Closed'

if __name__ == '__main__':
    unittest.main()

