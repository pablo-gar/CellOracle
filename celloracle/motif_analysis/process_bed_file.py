# -*- coding: utf-8 -*-
'''
This file contains custom functions for the analysis of ATAC-seq data.
Genomic activity information (peak of ATAC-seq) will be extracted first.
Then the peak DNA sequence will be subjected to TF motif scan.
Finally we will get list of TFs that potentially binds to a specific gene.

Codes were written by Kenji Kamimoto.


'''

###########################
### 0. Import libralies ###
###########################


# 0.1. libraries for fundamental data science and data processing

import pandas as pd
import numpy as np

import sys, os

from tqdm.auto import tqdm

# 0.2. libraries for DNA and genome data wrangling and Motif analysis
from genomepy import Genome

#from gimmemotifs.motif import Motif
from gimmemotifs.scanner import Scanner
from gimmemotifs.fasta import Fasta

from pybedtools import BedTool


####
### bed f

def check_peak_format(peaks_df, ref_genome, genomes_dir=None):
    """
    Check peak format.
     (1) Check chromosome name.
     (2) Check peak size (length) and remove sort DNAs (<5bp)

    Args:
        peaks_df (pandas.DataFrame):
        ref_genome (str): Reference genome name.   e.g. "mm9", "mm10", "hg19" etc
        genomes_dir (str): Installation directory of Genomepy reference genome data.

    Returns:
        pandas.DataFrame: Peaks data after filtering.

    """

    df = peaks_df.copy()

    n_peaks_before = df.shape[0]

    # Decompose peaks and make df
    decomposed = [decompose_chrstr(peak_str) for peak_str in df["peak_id"]]
    df_decomposed = pd.DataFrame(np.array(decomposed))
    df_decomposed.columns = ["chr", "start", "end"]
    df_decomposed["start"] = df_decomposed["start"].astype(np.int)
    df_decomposed["end"] = df_decomposed["end"].astype(np.int)

    # Load genome data
    genome_data = Genome(name=ref_genome, genomes_dir=genomes_dir)
    all_chr_list = list(genome_data.keys())


    # DNA length check
    lengths = np.abs(df_decomposed["end"] - df_decomposed["start"])


    # Filter peaks with invalid chromosome name
    n_threshold = 5
    df = df[(lengths >= n_threshold) & df_decomposed.chr.isin(all_chr_list)]

    # DNA length check
    lengths = np.abs(df_decomposed["end"] - df_decomposed["start"])

    # Data counting
    n_invalid_length = len(lengths[lengths < n_threshold])
    n_peaks_invalid_chr = n_peaks_before - df_decomposed.chr.isin(all_chr_list).sum()
    n_peaks_after = df.shape[0]

    #
    print("Peaks before filtering: ", n_peaks_before)
    print("Peaks with invalid chr_name: ", n_peaks_invalid_chr)
    print("Peaks with invalid length: ", n_invalid_length)
    print("Peaks after filtering: ", n_peaks_after)

    return df

def decompose_chrstr(peak_str):
    """
    Take peak name as input and return splitted strs.

    Args:
        peak_str (str): peak name.

    Returns:
        tuple: splitted peak name.

    Examples:
       >>> decompose_chrstr("chr1_111111_222222")
       "chr1", "111111", "222222"
    """
    *chr_, start, end = peak_str.split("_")
    chr_ = "_".join(chr_)

    return chr_, start, end

def list_peakstr_to_df(x):
    """
    Convert list of peaks(str) into data frame.

    Args:
       x (list of str): list of peak names

    Returns:
       pandas.dataframe: peak info as DataFrame

    Examples:
       >>> x = ['chr1_3094484_3095479', 'chr1_3113499_3113979', 'chr1_3119478_3121690']
       >>> list_peakstr_to_df(x)
                   chr	start	end
            0	chr1	3094484	3095479
            1	chr1	3113499	3113979
            2	chr1	3119478	3121690
    """
    df = np.array([decompose_chrstr(i) for i in x])
    df = pd.DataFrame(df, columns=["chr", "start", "end"])
    df["start"] = df["start"].astype(int)
    df["end"] = df["end"].astype(int)
    return df

def df_to_list_peakstr(x):

    x = x.rename(columns={"chrom":"chr"})

    peak_str = x.chr + "_" + x.start.astype(str) + "_" + x.end.astype(str)
    peak_str = peak_str.values

    return peak_str

####
###



def peak_M1(peak_id):
    """
    Take a peak_id (index of bed file) as input,
    then subtract 1 from Start position.

    Args:
        peak_id (str): Index of bed file. It should be made of "chromosome name", "start position", "end position"
            e.g. "chr11_123445555_123445577"
    Returns:
        str: Processed peak_id.

    Examples:
        >>> a = "chr11_123445555_123445577"
        >>> peak_M1(a)
        "chr11_123445554_123445577"
    """
    chr_, start, end = decompose_chrstr(peak_id)
    return chr_ + "_" + str(int(start)-1) + "_" + end


def peak2fasta(peak_ids, ref_genome, genomes_dir):

    '''
    Convert peak_id into fasta object.

    Args:
        peak_id (str or list of str): Peak_id.  e.g. "chr5_0930303_9499409"
            or it can be a list of peak_id.  e.g. ["chr5_0930303_9499409", "chr11_123445555_123445577"]

        ref_genome (str): Reference genome name.   e.g. "mm9", "mm10", "hg19" etc

        genomes_dir (str): Installation directory of Genomepy reference genome data.

    Returns:
        gimmemotifs fasta object: DNA sequence in fasta format

    '''
    genome_data = Genome(ref_genome, genomes_dir=genomes_dir)

    def peak2seq(peak_id):
        chromosome_name, start, end = decompose_chrstr(peak_id)
        locus = (int(start),int(end))

        tmp = genome_data[chromosome_name][locus[0]:locus[1]]
        name = f"{tmp.name}_{tmp.start}_{tmp.end}"
        seq = tmp.seq
        return (name, seq)


    if type(peak_ids) is str:
        peak_ids = [peak_ids]

    fasta = Fasta()
    for peak_id in peak_ids:
        name, seq = peak2seq(peak_id)
        fasta.add(name, seq)

    return fasta

def remove_zero_seq(fasta_object):
    """
    Remove DNA sequence with zero length
    """
    fasta = Fasta()
    for i, seq in enumerate(fasta_object.seqs):
        if seq:
            name = fasta_object.ids[i]
            fasta.add(name, seq)
    return fasta


def read_bed(bed_path):
    """
    Load bed file and return as dataframe.

    Args:
        bed_path (str): File path.

    Returns:
        pandas.dataframe: bed file in dataframe.

    """
    tt = BedTool(bed_path).to_dataframe().dropna(axis=0)
    tt["seqname"] = tt.chrom + "_" + tt.start.astype("int").astype("str") + "_" + tt.end.astype("int").astype("str")
    return tt
