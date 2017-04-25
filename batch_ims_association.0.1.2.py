#!/usr/bin/python

import sys, getopt
import requests
from requests.auth import HTTPBasicAuth
import json
import base64
#import grequests # Asynchronous requests. Replace 'requests' module.
#TODO: Replace synchronous requests by asynchonous requests.
#TODO: Use threads?

rest_api_prefix = None
user = None
password = None

def set_configurations(configurations_file=None):
    if configurations_file is None:
        configurations_file = '/home/lmonteiro/Documents/scripts/SM/configurations.json'
    try:
        with open(configurations_file) as f:
            configurations = json.load(f)
    except Exception:
        print 'There was an error while reading configurations file "{0}".'.format(configurations_file)
        return False
    global rest_api_prefix, user, password
    rest_api_prefix = configurations['rest_api_prefix']
    user = configurations['authentication']['user']
    password = base64.b64decode(configurations['authentication']['password']).decode('ascii')
    return configurations

def make_http_request(url, content=None, http_method='GET', request_timeout=1):
    max_attempts = 3
    attempts = 0
    while attempts < max_attempts:
        try:
            if http_method.upper() == 'GET':
                response = requests.get(url, auth=(user, password)) #TODO: Include timeout.
            elif http_method.upper() in ['POST', 'PUT']:
                if content is None:
                    print 'HTTP {0} request withouth content.'.format(http_method.upper())
                    break
                response = requests.post(url,
                                         auth=(user, password),
                                         json=content) #TODO: Include timeout.
            else:
                print 'I don\'t know how to work with this method: {0}.'.format(http_method.upper())
                break
            attempts += 1
        except ReadTimeout:
            print 'Request timed out.'
            continue
        except Exception:
            print 'Unknown error.'
            continue
            
        # Check response's status code.
        if response.status_code == 200:
            return { 'successful_request': True,
                     'response': response }
        elif response.status_code == 401:
            print 'Unauthorized request, check your credentials.'
        elif response.status_code == 404:
            print 'Something was not found.' #TODO: Improve this.
        break # New attempts will not be done.
        
    print 'Request aborted. {0} failed attempts.'.format(attempts)
    return { 'successful_request': False,
             'response': None } #TODO: Return something like the 'is_association_allowed()' method.
    
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
        why_not.append('Dependent incident ({0}) and source incident ({1}) can not be on the same queue.'
                       .format(dependent_incident['IncidentID'], source_incident['IncidentID']))
    
    if dependent_incident['IncidentID'] == source_incident['IncidentID']:
        is_allowed = False
        why_not.append('{0} can not be associated to itself.'
                       .format(dependent_incident['IncidentID']))
    
    # This kind of return must be kept, because it was defined in our meeting.
    return { dependent_incident['IncidentID']: is_allowed if is_allowed else why_not }
    
#TODO: Check if incident exist.
def get_incident_details(incident_id):
    url = '{0}/incidents?IncidentID={1}&view=expand'.format(rest_api_prefix, incident_id)
    result = make_http_request(url)
    print 'Getting {0} details.'.format(incident_id)
    if result['successful_request'] is True:
        return json.loads(result['response'].text)['content'][0]['Incident']
    return None

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
    return result['successful_request']

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
    return result['successful_request']

def associate_incident_set_to_source(source_incident_id, dependent_incidents_ids):
    successful_associations = []
    skipped_associations = []
    unsuccessful_updates = []
    pending_status = 'Pending IM'
    
    for dependent_incident_id in dependent_incidents_ids:
        source_incident = get_incident_details(source_incident_id)
        if source_incident is None:
            print 'Error while getting source incident ({0})'.format(source_incident_id)
            skipped_associations = dependent_incidents_ids # All associations will be skipped.
            break
            
        dependent_incident = get_incident_details(dependent_incident_id)
        if dependent_incident is None:
            skipped_associations.append(dependent_incident)
            continue
            
        response = is_association_allowed(source_incident,
                                          dependent_incident)
        if response[dependent_incident_id] is not True:
            skipped_associations.append(response)
            continue
            
        response = associate_incidents(source_incident_id,
                                       dependent_incident_id)
        if response is False:
            skipped_associations.append(dependent_incident_id)
            continue
        successful_associations.append(dependent_incident_id)
        
        response = update_incident_status(dependent_incident_id, pending_status)
        if response is not True:
            error_message = ('{0} was associated with {1}, however it'
                             ' was not possible to update its status to {2}.'
                             .format(dependent_incident_id, source_incident_id, pending_status))
            print error_message
            unsuccessful_updates.append({ dependent_incident_id: error_message })
        
    return {
             'successful_associations': successful_associations,
             'skipped_associations': skipped_associations,
             'unsuccessful_updates': unsuccessful_updates
           }

def print_association_statistics(successful_associations, skipped_associations, unsuccessful_updates):
    print '{0}{1} {2} {1}{0}'.format('\n', '=' * 7, 'Association Statistics')
    print '> Total successful associations: {0}.'.format(len(successful_associations))
    print '> Total skipped associations: {0}.'.format(len(skipped_associations))
    print '> Total unsuccessful status updates: {0}.'.format(len(unsuccessful_updates))
    
    print '> Skipped associations:'
    for skipped_association in skipped_associations:
        for dependent_incident_id, reasons in skipped_association.items():
            print '\n\tIncident: {0}'.format(dependent_incident_id)
            print '\tReasons {0}\n'.format('\n\t\t'.join(reasons))
    
    print '> Successful associations:\n'
    for successful_association in successful_associations:
        print '\t{0}'.format(successful_association)
        
    print '> Unsuccessful updates:\n'
    for unsuccessful_update in unsuccessful_updates:
        pass #TODO: Print data.

#TODO: Implement it.
def usage():
    pass

if __name__ == "__main__":
    source_incident_id = None
    dependent_incidents_ids = None
    configurations_file = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:d:c:',
                                   ['source=', 'dependents=', 'configurations='])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
        
    for opt, arg in opts:
        if opt in ['-s', '--source']:
            source_incident_id = arg
        elif opt in ['-d', '--dependents']:
            dependent_incidents_ids = [i.strip() for i in arg.strip(',').split(',')]
        elif opt in ['-c', '--configurations']:
            configurations_file = arg
        elif opt in ['-v', '--verbose']:
            pass #TODO: implement it.
    
    if set_configurations(configurations_file) is False:
        print 'Execution aborted.'
        sys.exit(1)
        
    dependent_incidents_ids = list(set(dependent_incidents_ids)) # remove repeated incidents
    association_statistics = associate_incident_set_to_source(
                                source_incident_id,
                                dependent_incidents_ids)
    print_association_statistics(association_statistics['successful_associations'],
                                 association_statistics['skipped_associations'],
                                 association_statistics['unsuccessful_updates'])
    sys.exit(0)
