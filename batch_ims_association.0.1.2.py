#!/usr/bin/python

import sys, getopt
import requests
from requests.auth import HTTPBasicAuth
import json
#import grequests # Asynchronous requests. Replace 'requests' module 
#TODO: Replace synchronous requests by asynchonous requests

#TODO: Check if incidents exist.
def get_incident_details(incident_id):
    url = 'http://qa.user.app-server.sm.intranet:13500/SM/9/rest/incidents?IncidentID={0}&view=expand'
          .format(incident_id)
    response = requests.get(url, auth=('svcacc_ws_ps_int', 'mudar$123')) #TODO: Include timeout.
    return json.loads(response.text)['content'][0]['Incident']
    
def is_association_allowed(source_incident, dependent_incident):
    forbidden_services = ['swap', 'disk_usage'] # Dependent incidents with these services can not be associated.
    dependent_incident_service = dependent_incident['BriefDescription'][1]
    is_allowed = True
    why_not = [] # Reasons why the association is not allowed.
    
    if dependent_incident_service in forbidden_services:
        is_allowed = False
        why_not.append('{0} is about {1}.'
                       .format(dependent_incident['IncidentID'], dependent_incident_service))
    
    if dependent_incident['Severity'] in range(1, 3):
        is_allowed = False
        why_not.append('{0} is P{1}.'
                       .format(dependent_incident['IncidentID'], dependent_incident['Severity']))
    
    if dependent_incident['PrimaryAssignmentGroup'] == source_incident['PrimaryAssignmentGroup']:
        is_allowed = False
        why_not.append('Dependent incident ({0}) and source incident ({1}) can not be in the same queue.'
                       .format(dependent_incident['IncidentID'], source_incident['IncidentID']))
    
    if dependent_incident['IncidentID'] == source_incident['IncidentID']:
        is_allowed = False
        why_not.append('{0} can not be associated to itself.'
                       .format(dependent_incident['IncidentID']))
    
    return { dependent_incident['IncidentID']: is_allowed if is_allowed else why_not }
    
def update_incident_status(incident_id, new_status):
    url = 'http://qa.user.app-server.sm.intranet:13500/SM/9/rest/incidents/{0}/action/update'
          .format(incident_id)
          
    incident_update = { 'Incident': {
                            'AssigneeName': 'svcacc_ws_ps_int',
                            'IMTicketStatus': new_status,
                            'update.action': incident_id
                        }
                      }
    maximum_attempts = 3
    attempts = 0
    error_messages = []
    while attempts < maximum_attempts:
        try:
            response = requests.post(url,
                                 auth=('svcacc_ws_ps_int', 'mudar$123'),
                                 json=incident_update)
            print 'Updating {0} status to {1}.'.format(incident_id, new_status)
            #print 'HTTP status code: {0}.'.format(response.status_code)
            if response.status_code == 200:
                return True
            attempts += 1
        except ReadTimeout:
            error_messages.append('Request timed out.')
        except Exception:
            error_messages.append('Unknown error while updating {0} status.'
                                  .format(incident_id))
        print error_messages[len(error_messages) - 1]
        
    return { incident_id: error_messages }

def associate_incidents(source_incident_id, dependent_incident_id):
    url = 'http://qa.user.app-server.sm.intranet:13500/SM/9/rest/screlations'
    
    new_association = { 'screlation': {
                            'Depend': dependent_incident_id,
                        	'Depend_Filename': 'problem',
                            'Source': source_incident_id,
                            'Source_Filename': 'problem'
                        }
                      }
    maximum_attempts = 3
    attempts = 0
    error_messages = []
    while attempts < maximum_attempts:
        try:
            response = requests.post(url,
                                     auth=('svcacc_ws_ps_int', 'mudar$123'),
                                     json=new_association)
            print 'Associating incidents {0} and {1}.'
                  .format(dependent_incident_id, source_incident_id)
            #print 'HTTP status code: {0}.'.format(response.status_code)
            #print 'Message: {0}\n'.format(response.text)
            if response.status_code == 200:
                return { dependent_incident_id: True }
            attempts += 1
        except ReadTimeout:
            error_messages.append('Request timed out.')
        except Exception:
            error_messages.append('Unknown error while associating {0} with {1}.'
                                  .format(dependent_incident_id, source_incident_id))
        print error_messages[len(error_messages) - 1]
    return { dependent_incident_id: error_messages }

def associate_incident_set_to_source(source_incident_id, dependent_incidents_ids):
    successful_associations = []
    skipped_associations = []
    pending_status = 'Pending IM'
    
    for dependent_incident_id in dependent_incidents_ids:
        response = is_association_allowed(get_incident_details(source_incident_id),
                                          get_incident_details(dependent_incident_id))
        if response[dependent_incident_id] is not True:
            skipped_associations.append(successful_association)
            continue
            
        response = associate_incidents(source_incident_id,
                                       dependent_incident_id):
        if response[dependent_incident_id] is True:
            successful_associations.append(dependent_incident_id)
            update_incident_status(dependent_incident_id, pending_status)
        
    return {
             'successful_associations': successful_associations,
             'skipped_associations': skipped_associations
           }

def print_association_statistics(successful_associations, skipped_associations):
    print '{0}{1} {2} {1}{0}'.format('\n', '=' * 7, 'Association Statistics')
    print '> Total successful associations: {0}.'.format(len(successful_associations))
    print '> Total skipped associations: {0}.'.format(len(skipped_associations))
    
    print '> Skipped associations:'
    for skipped_association in skipped_associations:
        for dependent_incident_id, reasons in skipped_association.items():
            print '\n\tIncident: {0}'.format(dependent_incident_id)
            print '\tReasons {0}\n'.format('\n\t\t'.join(reasons))
    
    print '> Successful associations:\n'
    for successful_association in successful_associations:
        print '\t{0}'.format(successful_association)

#TODO: Implement it.
def usage():
    pass

if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:d:', ['source=', 'dependents='])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
        
    for opt, arg in opts:
        if opt in ['-s', '--source']:
            source_incident_id = arg
        elif opt in ['-d', '--dependents']:
            dependent_incidents_ids = [i.strip() for i in arg.strip(',').split(',')]
        elif opt in ['-v', '--verbose']:
            pass #TODO: implement it.
    
    #print 'Source incident: {0}'.format(source_incident)
    #print 'Dependent incidents: {0}'.format(', '.join(dependent_incidents))
    #sys.exit(0)
    
    association_statistics = associate_incident_set_to_source(
                                source_incident_id,
                                dependent_incidents_ids)
                                
    print_association_statistics(association_statistics['successful_associations'],
                                 association_statistics['skipped_associations'])
    sys.exit(0)
