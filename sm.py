#!/usr/bin/python

def is_association_allowed(dependent_incident, source_incident):
    forbidden_services = ['swap', 'disk_usage']
    
    if dependent_incident['Severity'] in range(1, 3):
        return False
    if dependent_incident['BriefDescription'].split()[1] in forbidden_services:
        return False
    if dependent_incident['PrimaryAssignmentGroup'] == source_incident['PrimaryAssignmentGroup']:
        return False
        
    return True
