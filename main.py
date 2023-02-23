# import tools for working with xml, csv, and tables
from lxml import etree as et
import csv
import folium
from geopy.geocoders import Nominatim
import re

# a dict to store conversion of street type abbreviations such as 'Ave' to 'Avenue'
street_types = {
    'Ave': 'Avenue',
    'Blvd': 'Boulevard',
    'Cir': 'Circle',
    'Ct': 'Court',
    'Dr': 'Drive',
    'Ln': 'Lane',
    'N': 'North',
    'Ne': 'Northeast',
    'Nw': 'Northwest',
    'Pky': 'Parkway',
    'Pl': 'Place',
    'Rd': 'Road',
    'S': 'South',
    'Se': 'Southeast',
    'Sw': 'Southwest',
    'St': 'Street',
    'W': 'West',
}
# a lowercase version of the street_types dict and reverse the key/value pairs
street_types_lower = {k.lower(): v.lower() for k, v in street_types.items()}
print(street_types_lower)


# parse the csv file and in the first column, replace the street type abbreviations with the full name
# for example, 'Ave' will be replaced with 'Avenue'
# this is done to ensure that the address is parsed correctly
def parse_address(address):
    # to lower
    address = address.lower()
    # remove leading/trailing whitespace
    address = address.strip()
    # remove any punctuation
    address = re.sub(r'[^\w\s]', '', address)
    # split the address into a list
    parts = address.split()
    # skip if the address is empty
    if not parts or len(parts) < 1:
        return address
    # separate the street number from the rest of the address
    street_number = parts[0]
    street_parts = parts[1:]

    # sort out the unit number
    # if the last part is a number or one char long, it is probably a unit number
    if len(street_parts) > 1 and (street_parts[-1].isdigit() or len(street_parts[-1]) == 1):
        unit_number = street_parts[-1]
        street_number = ','.join(
            [street_number, unit_number])  # join the street number and unit number with a comma.
        # TODO: when matching for the street number, also match for the unit number (e.g. "123,A")
        street_parts = street_parts[:-2]  # redefine street_parts omitting the last two parts

    # if the first part is a street type abbreviation, replace it with the full name
    if street_parts[0].lower() in street_types_lower:
        street_parts[0] = street_types_lower[street_parts[0]]

    # if the last part is a street type abbreviation, replace it with the full name
    if street_parts[-1].lower() in street_types_lower:
        street_parts[-1] = street_types_lower[street_parts[-1]]

    # join the street parts back together
    street_name = ' '.join(street_parts)
    # join the address back together
    address = ' '.join([street_number, street_name])
    # return the new address
    return address


# function to parse the csv file looking in the first column for the address
# and in the third column for the number of dwelling units
# return a dict with the address as the key and the number of dwelling units as the value

def extract_csv_data(filename):
    dwelling_dict = {}
    # open the csv file
    with open(filename, 'r') as f:
        # read the csv file
        reader = csv.reader(f)
        # skip the first row
        next(reader)
        # loop through the rows
        for row in reader:
            # if the row is empty, skip it
            if not row:
                continue
            # parse the address
            address = parse_address(row[0])
            if len(address) < 5:
                continue

            dwelling_units = row[2]
            dwelling_dict[address] = dwelling_units

    # return the sorted dict
    return dict(sorted(dwelling_dict.items()))


# get just the osm data we are interested in; any element with a street address
def extract_osm_data(filename):
    # open the xml file
    with open(filename, 'r', encoding='utf-8') as f:
        # read the xml file
        tree = et.parse(f)
        # create a dict with addresses as keys and number of dwelling units as values
        address_dict = {}
        # collect any element which has a child element with the tag 'tag' and the attribute 'k' with the value 'addr:street'
        building_elements = tree.xpath("//node|//way[descendant::tag[@k='addr:street' or @k='addr:housenumber']]")
        for element in building_elements:
            id = str(element.get('id'))
            tag_elements = element.xpath("tag[@k='addr:street' or @k='addr:housenumber']")
            tags = {}
            for tag in tag_elements:
                tags[tag.get('k')] = tag.get('v')
            if len(tags) > 1:
                address = ' '.join([tags['addr:housenumber'], tags['addr:street']]).lower()
                # add id:address to the dict
                address_dict[id] = address
    return address_dict


# function to append the number of dwelling units to the osm xml file
def append_xml(xml_file, element_dict, input_dict, output_dict):
    # loop through the input dict and find the matching address in the element dict
    # if there is a match, add the dwelling units tag to the element of the original xml file by its id and save
    # the new xml file
    xml_tree = et.parse(xml_file)
    node_count = 0
    way_count = 0
    for id, address in element_dict.items():
        if address in input_dict:
            node_element = xml_tree.find(f".//*[@id='{id}']")
            if node_element is None:
                continue
            output_dict[id] = address
            matched_element = node_element[0]
            # print(f"found {matched_element.tag} {id} at {address} in the input dict, "
            #       f"with {input_dict[address]} dwelling units")

            if matched_element == 'way':
                way_count += 1
            elif node_element[0].tag == 'node':
                node_count += 1

            new_tag = et.Element('tag', k='dwelling_units', v=input_dict[address])
            node_element.append(new_tag)
    # save the new xml file
    # print(f"found {node_count} nodes and {way_count} ways with addresses in the input dict")
    xml_tree.write('portland_dwelling_units.osm', encoding='utf-8', xml_declaration=True)


# make a map of the addresses
def map_addresses(address_dict):
    geolocator = Nominatim(user_agent="map_addresses")
    city = 'portland'
    location = geolocator.geocode(city)
    map_center = (45.508512, -122.649411)
    m = folium.Map(location=map_center, zoom_start=12)
    mapped_addresses = 0
    max_addresses = 600
    for id, address in address_dict.items():
        if mapped_addresses > max_addresses:
            break
        mapped_addresses += 1
        location = geolocator.geocode(address)
        if location is not None:
            lat, lon = location.latitude, location.longitude
            popup_text = f"{address}\n({id})"
            folium.Marker([lat, lon], popup=popup_text).add_to(m)
    m.save('map.html')
    m.show_in_browser()


if __name__ == '__main__':
    # parse the csv file
    csv_dict = extract_csv_data('data.csv')
    # append the xml file
    xml_dict = extract_osm_data('data.xml')
    print(f"Found {len(xml_dict)} addresses in the xml file")
    # pprint.pprint(xml_dict)
    addresses = {}
    append_xml('data.xml', xml_dict, csv_dict, addresses)

    # map the addresses
    map_addresses(addresses)
