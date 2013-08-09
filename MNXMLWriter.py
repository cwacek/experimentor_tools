#!/opt/local/bin/pypy-c

from pygraph.classes.graph import graph
import string
import argparse
import pygraph.readwrite.markup as xmlwriter
import sys
import re

def get_attribute(graph,element,attr,cast=str):
    if isinstance(element, basestring):
        function = graph.node_attributes
    else:
        function = graph.edge_attributes
    return [cast(attrib[1]) for attrib in function(element) if attrib[0] == attr]

def write(gr,out):
    writer = MNXMLWriter(gr,out)
    writer.write_header()
    writer.write_vertices()
    writer.write_edges()
    writer.write_specs()
    writer.write_close()


def BYTES2BITS(x):
   return float(x) * 8

class MNXMLWriter():

    IPREGEX = "([0-9]{1,3}_){3}[0-9]{1,3}"
    CLIREGEX = "client_node_[0-9]+"
    DSTREGEX = "dest_node_[0-9]+"

    def __init__(self,gr,out):
        self.gr = gr
        self.out = out
        self.vertices = dict()
        self.vert_indices = dict()

    def write_close(self):
        self.out.write("</topology>\n")

    def write_header(self):
        self.out.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        self.out.write('<topology>\n')

    def write_vertices(self):
        vertIdx = 0
        vertNum = 0
        self.out.write('<vertices>\n')
        for vertex in self.gr.nodes():
            self.vertices[vertex] = (vertIdx,vertNum)
            self.vert_indices[vertNum] = (vertIdx,vertex)
            if (re.match(MNXMLWriter.IPREGEX,vertex) or
                re.match(MNXMLWriter.CLIREGEX,vertex) or
                re.match(MNXMLWriter.DSTREGEX,vertex)):
                #This is a IP (virtual node)
                self.out.write('<vertex int_idx="%s" role="virtnode" int_vn="%s" %s/>\n' %
                                 (vertIdx,vertNum,self.__node_info(vertex)))
                                #(vertIdx,vertNum,""))
                vertNum += 1
            else:
                self.out.write('<vertex int_idx="%s" role="gateway"/>\n' % (vertIdx))

            vertIdx += 1

        self.out.write('</vertices>\n')

    def __node_info(self,vertex_id):
        printset = {'bandwidth (kb/s)':'bw',
                    'ip address':'ip_address',
                    'router name':'nickname',
                    'as':'as',
                    'nodetype':'nodetype',
                    'flag - exit':'exit',
                    'flag - authority':'authority'
                   }
        return " %s " % (" ".join(["%s='%s'" % (printset[x[0]],x[1])
                                    for x in self.gr.node_attributes(vertex_id)
                                    if x[0] in printset.keys()]))

    def __get_spec(self,edge):
        if (not re.match(MNXMLWriter.IPREGEX,edge[0])
            and not re.match(MNXMLWriter.IPREGEX,edge[1])
            and (not re.match(MNXMLWriter.CLIREGEX,edge[0])
                and not re.match(MNXMLWriter.CLIREGEX,edge[1]))):
            return 'stub-stub'
        else:
            return 'client-stub'

    def __bandwidth_field(self,edge):
        if re.match(MNXMLWriter.IPREGEX,edge[0]):
            return get_attribute(self.gr,edge[0],"bandwidth (kb/s)")
        if re.match(MNXMLWriter.IPREGEX,edge[1]):
            return get_attribute(self.gr,edge[1],"bandwidth (kb/s)")
        if re.match(MNXMLWriter.CLIREGEX,edge[0]):
            return (get_attribute(self.gr,edge[0],"download_bw"),
                    get_attribute(self.gr,edge[0],"upload_bw"))
        if re.match(MNXMLWriter.CLIREGEX,edge[1]):
            return (get_attribute(self.gr,edge[1],"upload_bw"),
                    get_attribute(self.gr,edge[1],"download_bw"))
        return None

    def write_edges(self):
        self.written = dict()
        self.out.write('<edges>')
        edgeIdx = {'client-stub':0,'stub-stub':0}
        allIdx = 0
        for edge in self.gr.edges():
            endpoint1 = self.vertices[edge[0]][0]
            endpoint2 = self.vertices[edge[1]][0]
            bw = self.__bandwidth_field(edge)
            if bw is None:
                dbw,ubw = "",""
            elif len(bw) == 1:
                ubw = 'dbl_kbps="%s"' % (BYTES2BITS(bw[0]))
                dbw = ubw
            elif len(bw) == 2:
                (bw1,bw2) = map(lambda x: BYTES2BITS(x[0]),bw) #We assume client BWs are provided in bits/s
                dbw = 'dbl_kbps="%s"' % bw1
                ubw = 'dbl_kbps="%s"' % bw2
            else:
                dbw,ubw = "",""


            line = string.Template(
                '<edge int_dst="$dst" int_src="$src" int_idx="$idx" specs="$spec" int_delayms="$latency" $bw/>\n')

            attrs = {'dst':endpoint1,
                     'src':endpoint2,
                     'idx':allIdx,
                     'spec':self.__get_spec(edge),
                     'latency':int(self.gr.edge_weight(edge)),
                     'bw':ubw
                    }

            if (endpoint1,endpoint2) not in self.written:
                self.out.write(line.substitute(attrs))
                self.written[(endpoint1,endpoint2)] = 1
                edgeIdx[self.__get_spec(edge)] += 1
                allIdx += 1

            # Print the reverse link
            attrs['dst'] = endpoint2
            attrs['src'] = endpoint1
            attrs['idx'] = allIdx
            attrs['bw'] = dbw

            if (endpoint2,endpoint1) not in self.written:
                self.out.write(line.substitute(attrs))
                self.written[(endpoint2,endpoint1)] = 1
                edgeIdx[self.__get_spec(edge)] += 1
                allIdx += 1

        self.out.write('</edges>\n')

    def write_specs(self):
        self.out.write('<specs xmloutbug="workaround">\n')
        self.out.write('<client-stub dbl_plr="0" dbl_kbps="10000000" int_delayms="0" int_qlen="100"/>\n')
        self.out.write('<stub-stub dbl_plr="0" dbl_kbps="10000000" int_delayms="0" int_qlen="100"/>\n')
        self.out.write('</specs>\n')

def main_fun(xmlgraphfile):

    with open(xmlgraphfile) as f:
        grstr = f.read()

    gr = xmlwriter.read(grstr)
    write(gr,sys.stdout)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('graph_xml',type=str,
                help="An XML file containing a graph representation created by TorTopology")

    args = parser.parse()

    try:
        main_fun(args.graph_xml[0])
    except IOError:
        sys.stderr.write("Failed to read '%s'" % args.graph_xml[0])


