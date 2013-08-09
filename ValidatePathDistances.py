import sys
import networkx as nx
import re
import argparse
import pdb
from lxml import etree
import random
import subprocess
from os.path import expanduser

HOPREGEX = re.compile("\s*<path\s+int_vndst=\"[0-9]+\"\s+int_vnsrc=\"[0-9]+\"\s+hops=\"([0-9 ]+)\"\s+/>")

def pairwise(iterable):
    import itertools
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)

"""
A dictionary that maps modelnet vertex idx values to 
the igraph internal index. Keys are modelnet vertex ids.
"""
vertidx = dict()
edgeidx = dict()

def alist_append(d,attr,val):
    try:
        d[attr].append(val)
    except KeyError:
        d[attr] = [val]

def lookup_mn_route(route_file,pair):
    """
    Lookup the modelnet path from a routefile from pair[0]
    to pair[1]

    We use grep because routefiles are insanely large, and
    loading the entire thing for a lookup will kill memory.
    """

    call = []
    call.append('/bin/grep')
    call.append('int_vndst=\"%d\" int_vnsrc=\"%d\"'% (pair[1][0],pair[0][0]))
    call.append(route_file)


    try:
        result = subprocess.check_output(call)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("Error: %s. Output: %s\n" % ( e.returncode, e.output))

    m = HOPREGEX.match(result)

    if not m:
        return None

    return map(int,m.groups()[0].split())

def allpairs(graph_file=None,wt_attr=None):
    """
    Print the shortest path for all nodes, using
    the attribute named <b>wt_attr</b> as the weighting
    function.
    """
    
    if graph_file is None and wt_attr is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("-w", help="Attribute to use for shortest path weight",
                            metavar="<weight attribute>")
        parser.add_argument("graph_file",help="Modelnet Graph File")
        args = parser.parse_args()

        graph_file = args.graph_file
        wt_attr = args.w

    gr = load_graph(graph_file)

    print '<?xml version="1.0" encoding="ISO-8859-1"?>'
    print '<allpairs>'

    numdone = 0
    
    sys.stderr.write("Routing Node %s" % str(numdone))
    
    for src in gr.nodes():
        if gr.node[src]['vn'] == -1:
            continue
        if wt_attr:
            sp = nx.single_source_dijkstra_path(gr,src,wt_attr)
        else: 
            sp = nx.single_source_shortest_path(gr,src)
        for dst in sp:
            if gr.node[dst]['vn'] == -1:
                continue
            if dst == src:
                continue
            
            path = sp[dst]
            hops = [gr[x][y]['int_idx'] for x,y in pairwise(path)]  

            print ('<path int_vndst="%d" int_vnsrc="%d" hops="%s"/>'
                    % (gr.node[dst]['vn'],
                       gr.node[src]['vn'],
                       " ".join(map(str,hops))))

        sys.stderr.write('\b'*len(str(numdone)))
        sys.stderr.write("%d" % int(numdone+1))
        numdone += 1
    print '</allpairs>'

def main_fun(graph_file,model_file,sample_size,route_file,mnp_bin):
    igraph = load_graph(graph_file)

    sample = select_sample(model_file,sample_size)

    sp = igraph.shortest_paths(igraph.vs,weights='int_delayms')
    sp_paths = [igraph.get_shortest_paths(node.index,weights='int_delayms') for node in igraph.vs]

    stats = dict()

    numdone = 0
    sys.stderr.write("Pairs processed: %d" % numdone)
    for pair in sample:
        if pair[0][0] == pair[1][0]:
            continue
        node1 = igraph.vs.select(vn_eq=pair[0][0])[0]
        node2 = igraph.vs.select(vn_eq=pair[1][0])[0]
        model_dist = sp[node1.index][node2.index]

        result = subprocess.check_output([expanduser(mnp_bin), pair[0][1],pair[1][1], "3"],
                                            stderr=open('/dev/null','w'))
        results = result.split('\n')[:-1]
        pings = map(lambda x: int(float(x.split()[7]))/2,results)
        pings.sort()
        if pings[1] != model_dist:

            if route_file:
                mn_path = __route2idxlist(igraph,pair,lookup_mn_route(route_file,pair))
                model_path = sp_paths[node1.index][node2.index]
            else:
                mn_path = "[Not Available]"
                model_path = "[Not Available]"

            print "(%s -> %s): Model: %d ms %s; Empirically: %d ms %s; " % (
                    pair[0],pair[1],model_dist,model_path,pings[1],mn_path)
            alist_append(stats,'diff',abs(pings[1] - model_dist))
            alist_append(stats,'pathlendiff',abs(len(model_path) - len(mn_path)))
            if len(model_path) == len(mn_path):
                alist_append(stats,'eqlpath_latencydiff',abs(pings[1] - model_dist))

        sys.stderr.write("\b"*len(str(numdone)))
        numdone += 1
        sys.stderr.write("%d" % numdone)
        sys.stderr.flush()

    print "Average latency difference: %d" % (sum(stats['diff'])/len(stats['diff']))
    print "Average path length difference: %s" %( sum(stats['pathlendiff'])/len(stats['pathlendiff'])) 
    print ("Average latency difference in equal length paths: %d" %
            (sum(stats('eqlpath_latencydiff'))/
                 len(stats('eqlpath_latencydiff'))))


def __route2idxlist(igraph,pair,route):
    """
    Given a modelnet route, return the sequence of nodes
    it passes through (using the internal representation
    idx as a node id)

    This effectively translates modelnet vertex ID's to 
    igraph IDs.
    """

    idxlist = []
    edges = igraph.es.select(int_idx_in=route)
    srcnode = igraph.vs.select(vn_eq=pair[0][0])[0].index
    idxlist.append(srcnode)

    while len(route) > 0:
        hop = route.pop(0)

        edge = edges.select(idx=hop)[0]
        if edge.source == idxlist[-1]:
            idxlist.append(edge.target)
        elif edge.target == idxlist[-1]:
            idxlist.append(edge.source)
        else:
            sys.stderr.write("Couldn't link path")

    return idxlist


def select_sample(model_file,sample_size):
    """
    Select sample_size pairs of 'tor_relay' virtnodes from 
    model_file and return them as a list of pairs
    """

    with open(model_file) as f:
        tree= etree.parse(f)

    virtnodes = [(int(x.get('int_vn')),x.get('vip')) 
                 for x in tree.xpath("//virtnode[@nodetype='tor_relay']")]

    if len(virtnodes) == 0:
        sys.stderr.write("Warning, found no virtual nodes in the model file\n")
        return

    set1 = random.sample(virtnodes,sample_size)
    set2 = random.sample(virtnodes,sample_size)

    del virtnodes
    return zip(set1,set2)

def load_graph(graph_file):
    
    with open(graph_file) as f:
        tree = etree.parse(f)
    
    nxgraph = nx.DiGraph()
    vertices = tree.xpath('//vertex')

    if len(vertices) == 0:
        sys.stderr.write("warning: didn't find any virtual nodes. did you prov_ide a .graph file as input?\n")
        return

    vertidx.clear()
    nodecount = 0
    for vertex in vertices:
        v_id = int(vertex.get('int_idx'))
        vtype='relay' if vertex.get('role') is not 'gateway' else 'pop'
        vnattr = int(vertex.get('int_vn')) if vertex.get('int_vn') else -1
        nxgraph.add_node(v_id,id=v_id,vn=vnattr,type=vtype)
        vertidx[v_id] = nodecount
        nodecount += 1

    del vertices

    edges = tree.xpath("//edge")

    for edge in edges:
        src = int(edge.get('int_src'))
        dst = int(edge.get('int_dst'))
        attrs = dict()
        for key in edge.keys():
            attrs[key] = edge.get(key)

        nxgraph.add_edge(src,dst,**attrs)

    del edges
    
    return nxgraph

if __name__ == "__main__":
    allpairs()
