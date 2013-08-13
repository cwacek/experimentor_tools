#!/usr/bin/env python

import os
import sys
import argparse
import pdb
import yaml
import random
import MNXMLWriter
import ModelFunctions

def mk_struct(node,*args):
    """
    Make a structure out of a node that contains an 'ip' element,
    and optionally, additional elements. 

    Additional elements can be specified as strings equivalent to 
    attribute names, or as lists. If as lists, the attribute name
    is assumed to be in the first position, and the second position
    the the key the attribute should be stored under.
    """
    ret = dict()
    ret['ip'] = node.get('vip')
    for arg in args:
        
        if isinstance(arg,basestring):
            ret[arg] = node.get(arg)
            if ret[arg] is None:
                ret[arg] = '0'
        else:
            ret[arg[1]] = node.get(arg[0])
            if ret[arg[1]] is None:
                ret[arg[1]] = '0'
    return ret

def extract_attributes(args):
    from lxml import etree

    with open(args.model_file) as f:
        tree = etree.parse(f)

    virtnodes = tree.xpath("//virtnode")
    if len(virtnodes) == 0:
        sys.stderr.write("Warning: didn't find any virtual nodes. Did you provide a .model file as input?\n")
    
    nodes = []
    for node in virtnodes:
      saved = dict()
      try:
        for (cond_attr,cond_val) in args.condition:
          try:
            if node.get( cond_attr ) != cond_val:
              raise RuntimeError
            else:
              saved[cond_attr] = node.get( cond_attr )
          except KeyError:
            raise RuntimeError
      except RuntimeError:
        continue
      
      for included in args.include:
        try:
          if node.get(included):
            saved[included] = node.get( included ) 
          else: raise KeyError()
        except KeyError:
            sys.stderr.write("Failed to include '%s' because it was not found in the model file.\n"%included)

      nodes.append(saved)

    print yaml.dump(nodes)


def extract_node_list(args):
    try:
        nodelist = build_node_list(args)
    except IOError as e:
        sys.stderr.write("Error: %s\n" % e)
        return

    # Shuffle so we get a random order of nodes in our resultant list.
    # This will hopefully make it better if we don't use all of the nodes in our sample
    # Arrange the relays in order of descending bandwidth so the distribution
    # we sample has a bit of everything.
    [random.shuffle(nodetype) for nodetype in nodelist.itervalues() if nodetype != 'relays']

    if args.num_relays != 'all':
        nodelist['relays'].sort(key=lambda x: float(x['bw']),reverse=True)
        nodelist['relays'] = choose_uniformly(nodelist['relays'],
                                              int(args.num_relays))

    if all(map(lambda node: node['exit'] != '1', nodelist['relays'])):
        sys.stderr.write("Warning: Did not select any exit nodes\n")

    if args.num_clients:
        tmp = random.sample(nodelist['clients'],args.num_clients)
        nodelist['clients'] = tmp

    for relay in nodelist['relays']:
        bw = relay['bw']
        avg_bw = relay['avg_bw']
        burst_bw = relay['burst_bw']
        relay['bw'] = str('%d %s'% (int(float(bw)),args.bw_units))
        relay['avg_bw'] = "%d %s"% (int(float(avg_bw)),args.bw_units)
        relay['burst_bw'] = "%d %s"% (int(float(burst_bw)),args.bw_units)


    sys.stderr.write("Wrote %s clients, %s destinations, %s relays,and %s authorities\n"
                        % (len(nodelist['clients']),len(nodelist['destinations']),
                            len(nodelist['relays']),len(nodelist['authorities'])))

    print yaml.dump(nodelist)

def choose_uniformly(l,n):
    """
    Choose n elements from l, by partitioning l
    into n buckets, and selecting one element at
    random from each bucket.

    The list elements chose will be in the same order
    as in l.

    @raise IndexError
    """
    ret = []
    for i,chunk in enumerate(_chunks(l,len(l)/n)):
        if i == n:
            break
        ret.append(random.choice(chunk))
    return ret

def _chunks(l,n):
    return (l[i:i+n] for i in xrange(0,len(l),n))

def build_node_list(args):
    from lxml import etree

    with open(args.model_file) as f:
        tree = etree.parse(f)

    nodelist = { 'clients':[],'destinations':[],'relays':[],'authorities':[] }
    virtnodes = tree.xpath("//virtnode")
    if len(virtnodes) == 0:
        sys.stderr.write("Warning: didn't find any virtual nodes. Did you provide a .model file as input?\n")
    for node in virtnodes:
        if node.get('nodetype') == 'client':
            nodelist['clients'].append(mk_struct(node))
        elif node.get('nodetype') == 'dest':
            nodelist['destinations'].append(mk_struct(node))
        elif (node.get('nodetype') == args.relay_nodetype
              and node.get(args.authority_key) != '1'):
            if args.min_relay_bandwidth and float(node.get('bw')) < args.min_relay_bandwidth:
                continue
            nodelist['relays'].append(mk_struct(node,'bw',(args.exit_key,'exit'),'avg_bw','burst_bw'))
        elif (node.get('nodetype') == args.relay_nodetype
              and node.get(args.authority_key) == '1'):
            nodelist['authorities'].append(mk_struct(node,'bw',(args.exit_key,'exit'),'avg_bw','burst_bw'))


    if len(nodelist['relays']) + len(nodelist['authorities']) == 0:
      sys.stderr.write("Warning: didn't find any relays. Did you "
                       "provide the correct relay nodetype?\n")
      sys.exit(1)

    return nodelist


def gen_modelnet_graph(args):
    try:
        MNXMLWriter.main_fun(args.graph_xml)
        sys.stderr.write("\n".join(["Successfully Wrote .graph file. Use the Modelnet tools 'allpairs'",
                         "and 'mkmodel' to generate topology files"]))
    except IOError:
        sys.stderr.write("Failed to read '%s'" % args.graph_xml)

def check_model(args):
    try:
        ModelFunctions.check_model(args.model_file)
    except IOError:
        sys.stderr.write("Failed to read '%s'" % args.model_file)

def validate_distances(args):
    import ValidatePathDistances
    try:
        ValidatePathDistances.main_fun(args.graph_xml,
                                       args.model_xml,
                                       args.sample_size,
                                       args.route_xml,
                                       args.modelnetping_bin)
    except IOError as e:
        sys.stderr.write("%s" % e)

def main():
    parser = argparse.ArgumentParser()
    cmd_parser = parser.add_subparsers(title="Commands")

    guard_parser = cmd_parser.add_parser("extract_attribute_list", help="Extract a yaml file containing nodes with the specified attributes")
    guard_parser.add_argument("model_file",help="The ModelNet model file")
    guard_parser.add_argument("--condition",help="The condition to be satisfied. e.g. --condition Guard 1' would include only nodes with "
                              +"a Guard attibute with the value 1. This can be specified "+
                              "multiple times and the conditions will be ANDed together.", nargs=2,action="append")
    guard_parser.add_argument("--include",help="The additional attributes to include for each node",action="append")
    guard_parser.set_defaults(func=extract_attributes)

    xnl_parser = cmd_parser.add_parser('extract_node_list',
                            help="Extract a node list for use with ExperimenTor")
    xnl_parser.add_argument("model_file",help="The ModelNet model file")
    xnl_parser.add_argument("-r","--num_relays", type=str,
                            help="Select NUM_RELAYS relays from the list at random")
    xnl_parser.add_argument("-c","--num_clients", type=int,
                            help="Select NUM_RELAYS clients from the list at random")
    xnl_parser.add_argument("-b","--min_relay_bandwidth",type=int,
                            help="Only print relays with bandwidth greater than this value")
    xnl_parser.add_argument('--relay_nodetype',type=str,
                            default='tor_relay',
                help="The nodetype of Tor relays in the model. Defaults to 'tor_relay'")
    xnl_parser.add_argument('--bw_units',type=str,
                            default='bytes',
                            help="The units the bw numbers are measured in")
    xnl_parser.add_argument('--exit_key',type=str,
                            default='exit',
                help="The name of the key used to designate exits in the model. Default: 'exit'")
    xnl_parser.add_argument('--authority_key',type=str,
                            default='authority',
                help="The name of the key used to designate authorities in the model. Default: 'authority'")

    xnl_parser.set_defaults(func=extract_node_list)

    gengr_parser = cmd_parser.add_parser('gen_modelnet_graph',
                            help="Generate a modelnet graph from a TorTopology xml file")
    gengr_parser.add_argument("graph_xml", help="The TorTopology xml file")
    gengr_parser.set_defaults(func=gen_modelnet_graph)

    validate_paths = cmd_parser.add_parser('validate_paths',
                            help="Validate that the latencies in the resultant topology are appropriate for the distances in the original graph")
    validate_paths.add_argument("graph_xml", help="The TorTopology xml file") 
    validate_paths.set_defaults(func=validate_distances)
    validate_paths.add_argument("model_xml",help="The ModelNet model file")
    validate_paths.add_argument("sample_size",help="The number of paths to sample and test",type=int)
    validate_paths.add_argument("route_xml",help="The ModelNet route file",nargs="?",default=None)
    validate_paths.add_argument("modelnetping_bin",
                     help="The path to modelnetping. Default: ~/routing-metrics/tcpping/modelnetping",
                     default="~/routing-metrics/tcpping/modelnetping",
                     nargs="?")

#    chk_model_parser =cmd_parser.add_parser("check_model",
#                            help="Check that a Model file appears to have the right number of hops etc.")
#    chk_model_parser.add_argument("model_file",help="The ModelNet model file")
#    chk_model_parser.set_defaults(func=check_model)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()




