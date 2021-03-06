from __future__ import division

import os, re, json
from email.parser import Parser
from email.header import decode_header
from bs4 import BeautifulSoup
import pandas as pd

PROJ_ROOT = os.environ.get('PROJ_ROOT')
with open(PROJ_ROOT+'parameters.json') as json_file:
    params = json.load(json_file)

trial = params['trial']
imap = params['IMAP']

DELIMETER = ','
NEWLINE = os.linesep

print("Found the following files in the data directory")
print(os.listdir(trial['EMAIL_DIR']))

ACCOUNT_LIST = imap['ACCOUNT_LIST']
print("Found the following accounts in the ACCOUNT_LIST")
print(ACCOUNT_LIST)

# Text Content Regex
phone_number_re = re.compile('\(?([0-9]{3})\)?([ .-]?)([0-9]{3})\2([0-9]{4})')
google_maps_re = re.compile('https:\/\/maps.google.com\/\?q=((\w|\d|\.|\,)+\+)+((\w|\d|\.|\,)+)')
trulia_listing_re = re.compile('www\.trulia\.com/rental/\d*')

def extract_hyperlinks(soup):
    link_set = set()
    all_a = soup.findAll("a")

    for link in all_a:
        if 'href' in link.attrs:
            if link.attrs['href'] != '#':   # Filter out empty '#' links
                link_set.add(link.attrs['href'])

    return list(link_set)

def extract_regex(set_of_strings, compiled_regex):
    match_set = set()

    for link in set_of_strings:
        m = compiled_regex.search(link)
        if m: # if there is a regex match
            match_set.add(m.group(0)) # add the match to the match_set

    return list(match_set)

def extract_single_regex(set_of_strings, compiled_regex):

    for link in set_of_strings:
        m = compiled_regex.search(link)
        if m: # if there is a regex match
            return m.group(0) # return it immediately

    return ''

def header_to_unicode_string(header):
    str_builder = ''

    decoded_tuples = decode_header(header)

    for decoded_tuple in decoded_tuples:
        if decoded_tuple[1]:
            str_builder += unicode(decoded_tuple[0], decoded_tuple[1]) + " "
        else:
            str_builder += decoded_tuple[0]

    return str_builder.strip()

def make_soup(msg):
    """
    Input: msg, email.message.EmailMessage
    Output: dict, {string feature_name: list feature_observation}
    """
    email = {feature:'' for feature in ['trulia','gmaps','tel','mailto','text_plain','text_html']}
    email['from'] = header_to_unicode_string(msg['From'])
    email['subject'] = header_to_unicode_string(msg['Subject'])
    email['message-id'] = msg['Message-ID']

    try:
        email['date'] = pd.to_datetime(msg['date']) 
    except:
        print("Message-ID: " + email['message-id'] + "\n\t contains an out of bounds datetime string")
        print(msg['date'])
        print("Datetime object being recorded as NaT")
        email['date']=pd.NaT

    for part in msg.walk():  # dept-first traversal of multipart hierarchy
        if part.get_content_type()=='text/plain':

            charset = part.get_content_charset(failobj='utf-8')  # Set 'utf-8' as default
            email['text_plain']= unicode(part.get_payload(decode=True),encoding=charset, errors='ignore')

        elif part.get_content_type()=='text/html':

            charset = part.get_content_charset(failobj='utf-8')  # Set 'utf-8' as default

            part_payload = part.get_payload(decode=True) # Decode according to the Content-Transfer-Encoding header

            # Use charset to specify from_encoding, if available
            if charset:
                soup = BeautifulSoup(part_payload, 'lxml', from_encoding=charset) 
            else:
                soup = BeautifulSoup(part_payload, 'lxml')

            links = extract_hyperlinks(soup)
            email['all_links'] = links
            email['all_trulia'] = [link for link in links if re.search('trulia',link)]
            email['trulia'] = extract_single_regex(links,trulia_listing_re)
            email['gmaps'] = extract_regex(links, google_maps_re)
            email['tel'] = [link.split(':')[1] for link in links if link.startswith('tel')]
            email['mailto'] = [link.split(':')[1] for link in links if link.startswith('mailto')]

            str_builder = ''
            if soup.body:
                for string in soup.body.stripped_strings:
                    str_builder+=string + NEWLINE
            else:
                for string in soup.stripped_strings:
                    str_builder+=string + NEWLINE
            email['text_html'] = str_builder
        else:
            continue

    # Select 'text/plain' only if navigable strings of 'text/html' is empty
    if email['text_html']=='':
        email['text']=email['text_plain']
    else:
        email['text']=email['text_html']

    return email

def get_text_alt(email):
    with open(trial['EMAIL_DIR']+email, 'rb') as open_email:
        msg = Parser().parse(open_email)
    for part in msg.walk():
        if part.get_content_type()=='text/html':
            charset = part.get_content_charset(failobj='utf-8')  # Set 'utf-8' as default
            part_payload = part.get_payload(decode=True) # Decode according to the Content-Transfer-Encoding header

            if charset:
                soup = BeautifulSoup(part_payload, 'lxml', from_encoding=charset)
            else:
                soup = BeautifulSoup(part_payload, 'lxml')

    all_p = soup.findAll('p')

    str_builder = ''
    for p in all_p:
        for string in p.stripped_strings:
            str_builder+=string+NEWLINE
    return str_builder

# Convert lists contained in dataframe into JSON encoded strings
def list_to_json_string(single_list):
    if single_list:
        return json.dumps(single_list)
    else:
        return ''
    
    
# GVoice specific Regex
gvoice_phone_re = re.compile('\(\d{3}\) \d{3}-\d{4}')
#gvoice_time_re = re.compile('(\d{1,2}:\d{2} [A|P]M)')
gvoice_text_re = re.compile('@txt.voice.google.com')
gvoice_text_subject_re = re.compile('<Subject: (.+)> - ')

def parse_gvoice_VM(vm_idx, all_emails):
    """
    Input: Index series of emails that match GVoice_VM filter
        Update any extracted fields to all_emails 
    Output: dataframe that was used to update all_emails 
    """
    
    emails = []
    
    file_handles = all_emails.loc[vm_idx,'email'].values
    for file_handle in file_handles:

        with open(trial['EMAIL_DIR'] + file_handle, 'rb') as open_email:
            msg = Parser().parse(open_email)
        email = {feature:'' for feature in ['text']} 
        email['subject'] = msg['Subject']

        for part in msg.walk():
            if part.get_content_type()=='text/html':
                charset = part.get_content_charset(failobj='utf-8')  # Set 'utf-8' as default
                part_payload = part.get_payload(decode=True) # Decode according to the Content-Transfer-Encoding header

                if charset:
                    soup = BeautifulSoup(part_payload, 'lxml', from_encoding=charset)
                else:
                    soup = BeautifulSoup(part_payload, 'lxml')    

                body = soup.body
                all_span = soup.findAll('span')
                email['text'] = ''.join([span.get_text() for span in all_span if span.string])
                tel_match = gvoice_phone_re.search(email['subject'])
                if tel_match:
                    email['tel'] = tel_match.group(0)
                else:
                    email['tel'] = ''
                
                email['response_type'] = 'voicemail'

                emails.append(email)
            
    gvoice_emails = pd.DataFrame(emails, index=vm_idx)
    
    all_emails.update(gvoice_emails)
    return pd.DataFrame(emails, index=vm_idx)

def parse_gvoice_text(text_idx, all_emails):
    """
    Input: Index series of emails that match GVoice_text filter
        Update any extracted fields to all_emails 
    Output: dataframe used to update all_emails
    """
    emails = []
    
    file_handles = all_emails.loc[text_idx,'email'].values
    for file_handle in file_handles:
        with open(trial['EMAIL_DIR'] + file_handle, 'rb') as open_email:
            msg = Parser().parse(open_email)
            email = {feature:'' for feature in ['text','response_type']} 
            email['subject'] = msg['Subject']
            
            tel_match = gvoice_phone_re.search(email['subject'])
            if tel_match:
                email['tel'] = tel_match.group(0)
            else:
                email['tel'] = ''

            for part in msg.walk():
                if part.get_content_type()=='text/html':
                    charset = part.get_content_charset(failobj='utf-8')  # Set 'utf-8' as default
                    part_payload = part.get_payload(decode=True) # Decode according to the Content-Transfer-Encoding header

                    if charset:
                        soup = BeautifulSoup(part_payload, 'lxml', from_encoding=charset)
                    else:
                        soup = BeautifulSoup(part_payload, 'lxml')    

                    body = soup.body
                    email['text'] = body.table.tr.td.contents[1].tr.td.contents[0]
                        
            subject_match = gvoice_text_subject_re.search(email['text'])
            if subject_match:
                email['subject'] = subject_match.group(1)
                email['text'] = email['text'][subject_match.end():] # Slice off 'subject' from 'text' field
            else:
                email['subject'] = ''

            emails.append(email)

    text_emails = pd.DataFrame(emails,index= text_idx)
    text_emails['response_type']='text'
    all_emails.update(text_emails)

    return text_emails

def parse_all(response_type):
    email_summary_cols = ['trulia', 'gmaps', 'tel', 'mailto', 'text']
    all_emails = pd.DataFrame(columns=email_summary_cols)

    email_folder_dir = trial['EMAIL_DIR']+response_type
    email_dict = {}
    for email in os.listdir(email_folder_dir):
        with open(os.path.join(email_folder_dir,email), 'rb') as open_email:
            msg = Parser().parse(open_email)
            email_dict[email] = make_soup(msg)

    return_df = pd.DataFrame(email_dict).T

    return_df['email']=return_df.index.values

    #split off account name
    return_df['account']=return_df['email'].apply(lambda x:x.split('.')[0])

    #then prepend 'response-type/' to email_name.eml
    return_df['email']=response_type+'/'+return_df['email']
    return_df['race'] = return_df['account'].apply(lambda x:params['account_to_race'][x])

    return return_df

def main():
    responses = parse_all(trial['EMAIL_PREFIX'] + '-Response')
    responses['response']=1

    nonresponses = parse_all(trial['EMAIL_PREFIX']+'-Nonresponse')
    nonresponses['response']=0

    all_emails = pd.concat([responses,nonresponses], ignore_index=True, sort=True)

    all_emails['trulia_bool']=0
    all_emails.loc[all_emails['trulia']!='','trulia_bool']=1

    print("Looking for email_ids.csv in " + trial['EMAIL_DIR'])
    email_ids = pd.read_csv(os.path.join(trial['EMAIL_DIR'],'email_ids.csv'))

    all_emails = pd.merge(all_emails, email_ids, on='email', how='left')

    print("{} emails processed".format(len(all_emails)))
    print("Email identifiers containing NULL values: ")
    print(all_emails[['message-id','X-GM-THRID','X-GM-MSGID']].isnull().sum())
    print("Emails with NULL entries for X-GM-MSGID")
    print(all_emails[all_emails['X-GM-MSGID'].isnull()]['email'].values)

    ## Removing Inline CSS style from body
    ## Parse Text separately when it appears like:
    ##   @media only screen and (max-width: 550px), scr... 

    # Filter for text
    selection_list = all_emails[all_emails['text'].str.startswith('@')]['email'].values

    # Transform filtered text
    text_replacement_dict = {}
    for email in selection_list:
        text_replacement_dict[email]=get_text_alt(email)

    # Overwite 'text' section with transformed text
    for email in text_replacement_dict.keys():
        all_emails.loc[all_emails['email']==email,'text'] = text_replacement_dict[email]


    list_columns = ['all_links','all_trulia','gmaps','mailto','tel']

    for col in list_columns:
        all_emails[col] = all_emails[col].apply(list_to_json_string)


    all_emails['response_type'] = 'email'
    
    # GVOICE and GTEXT
    # Parse GVoice voicemails
    # Select
    vm_idx = all_emails[all_emails['from']=='Google Voice <voice-noreply@google.com>']['email'].index
    # Parse and Overwrite matches
    vm_emails = parse_gvoice_VM(vm_idx, all_emails)


    # Parse GVoice texts
    # Select
    text_matches = all_emails['from'].apply(lambda x:gvoice_text_re.search(x))
    text_idx = text_matches.dropna().index
    # Parse and Overwrite matches
    text_emails = parse_gvoice_text(text_idx, all_emails)

    # Omit 'text_plain' and 'text_html' columns
    out_columns = [u'all_links', u'all_trulia', u'date', u'from', u'gmaps', u'mailto',
                   u'message-id', u'subject', u'tel', u'text', u'trulia', u'email', u'account',
                   u'race', u'response', u'trulia_bool', u'X-GM-MSGID', u'X-GM-THRID','response_type']

    # Write out to the trial's EMAIL_PARSED location 
    all_emails[out_columns].to_csv(trial['EMAIL_PARSED'],encoding='utf-8',index=False)

if __name__ == "__main__":
    main()
