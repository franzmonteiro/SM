#!/usr/bin/python

import sys, getopt
import requests
from requests.auth import HTTPBasicAuth
import json
import base64
#import grequests # Asynchronous requests. Replace 'requests' module 
#TODO: Replace synchronous requests by asynchonous requests
#TODO: Use threads?

rest_api_prefix = None
user = None
password = None

def set_configurations():
    configurations_file = '/home/lmonteiro/Documents/scripts/SM/configurations.json'
    with open(configurations_file) as f:
        configurations = json.load(f)
    global rest_api_prefix, user, password    
    rest_api_prefix = configurations['rest_api_prefix']
    user = configurations['authentication']['user']
    password = base64.b64decode(configurations['authentication']['password']).decode('ascii')
    return configurations

def make_http_request(url, content=None, http_method='GET', request_timeout=1):
    max_attempts = 3
    attempts = 0
    errors = []
    while attempts < max_attempts:
        try:
            error = {}
            error['is_unknown'] = False
            
            if http_method.upper() == 'GET':
                response = requests.get(url, auth=(user, password)) #TODO: Include timeout
            elif http_method.upper() == 'POST':
                if content is None:
                    error['message'] = 'POST request withouth content.'
                    #return False
                response = requests.post(url, auth=(user, password), json=content) #TODO: Include timeout
            else:
                print 'Unknown HTTP method.' #TODO: Improve this
            #
            if response.status_code == 200:
                return { 'successful_http_request': True,
                         'response': response }
            elif response.status_code == 401:
                error['message'] = 'Unauthorized request, check your credentials.'
            
            attempts += 1
            errors.append(error)
            if attempts < max_attempst:
                print 'Trying again ..'
            continue
        except ReadTimeout:
            error['message'] = 'Request timed out.'
        except Exception:
            error['is_unknown'] = True
            error['message'] = 'Unknown error while '
            
    print 'Request aborted. Three attempts failed.'
    return { 'successful_http_request': False,
             'response': errors }

#TODO: Check if incidents exist.
def get_incident_details(incident_id):
    url = '{0}/incidents?IncidentID={1}&view=expand'.format(rest_api_prefix, incident_id)
    result = make_http_request(url)
    if result['successful_request'] is True:
        response = result['response']
        return json.loads(response.text)['content'][0]['Incident']
    """print '> Error messages:'
    for error_message in result['error_messages']:
        if error_message is None:
            error_message = 'Unknown error while getting {0} details.'.format(incident_id)
        print error_message
    return False"""
    #TODO: Reorganize this.
    
def is_association_allowed(source_incident, dependent_incident):
    forbidden_services = ['swap', 'disk_usage'] # Dependent incidents with these services can not be associated.
    dependent_incident_service = dependent_incident['BriefDescription'].split()[1] #TODO: Use split() ?
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
    url = '{0}/incidents/{1}/action/update'.format(rest_api_prefix, incident_id)
    incident_update = { 'Incident': {
                            'AssigneeName': user,
                            'IMTicketStatus': new_status,
                            'update.action': incident_id
                        }
                      }
    result = make_http_request(url, content=incident_update, http_method='POST')
    print 'Updating {0} status to {1}.'.format(incident_id, new_status)
    #TODO: Use something like 'result.items()' to define a proper unknown error message.
    """for error_message in result['error_messages']:
        if error_message['is_unknown']
            error_message['is_unknown'] += ' updating {0} status.'.format(incident_id)"""
        
    return result

def associate_incidents(source_incident_id, dependent_incident_id):
    url = '{0}/screlations'.format(rest_api_prefix)
    new_association = { 'screlation': {
                            'Depend': dependent_incident_id,
                        	'Depend_Filename': 'problem',
                            'Source': source_incident_id,
                            'Source_Filename': 'problem'
                        }
                      }
    result = make_http_request(url, content=new_association, http_method='POST')
    print 'Associating incidents {0} and {1}.'.format(dependent_incident_id, source_incident_id)
    return result
    #'Unknown error while associating {0} with {1}.'.format(dependent_incident_id, source_incident_id))

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
                                       dependent_incident_id)
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
    
    set_configurations()
    dependent_incidents_ids = list(set(dependent_incidents_ids)) # remove repeated incidents
    #print 'Source incident: {0}'.format(source_incident)
    #print 'Dependent incidents: {0}'.format(', '.join(dependent_incidents))
    #sys.exit(0)
    
    association_statistics = associate_incident_set_to_source(
                                source_incident_id,
                                dependent_incidents_ids)
                                
    print_association_statistics(association_statistics['successful_associations'],
                                 association_statistics['skipped_associations'])
    sys.exit(0)
