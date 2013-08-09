from lxml import etree
import pdb


def check_model(modelfile):

    with open(modelfile) as f:
        tree = etree.parse(f)

    virtnodes = tree.xpath("//virtnode")
    hops = tree.xpath('//hop')

    pdb.set_trace()
    nodehash = dict()
    for node in virtnodes:
        nodehash[node.get('int_vn')] = dict()

    missing =[]

    for hop in hops:
        if hop.get('int_dst') in nodehash:
            nodehash[hop.get('int_dst')]['dst_hop'] = hop.get('int_idx')
        else:
            print "Hop %s has nonexistent dst %s" % (hop.get('int_idx'),hop.get('int_dst')) 
            missing.append(hop)
        
        if hop.get('int_src') in nodehash:
            nodehash[hop.get('int_src')]['src_hop'] = hop.get('int_idx')
        else:
            print "Hop %s has nonexistent src %s" % (hop.get('int_idx'),hop.get('int_src')) 
            missing.append(hop)

    goodnodes = filter(lambda x: any(['dst_hop' not in x[1],'src_hop' not in x[1]]),nodehash.iteritems())

    print "%s nodes missing hops; %s hops missing nodes" % (len(goodnodes),len(missing))

