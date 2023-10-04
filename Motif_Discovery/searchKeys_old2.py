#!/usr/bin/env python
#searchKeys.py
"""
	Searches for specific keys or amino acids or positions and retrieves 
	their details from triplets files
"""

import glob, os, csv, ntpath,socket,argparse, time, re
import pandas as pd, numpy as np
from collections import Counter
from joblib import Parallel, delayed, cpu_count
from os.path import expanduser
import itertools


__author__ = "Venkata Sarika Kondra"
__version__ = "1.0.1"
__maintainer__ = "Venkata Sarika Kondra"
__email__ = "c00219805@louisiana.edu"

parser = argparse.ArgumentParser(description='Search Keys.')
parser.add_argument('--sample_name', '-sample', metavar='sample_name', \
	default='t1', \
	help='Name of the sample on which this script should be run.')
parser.add_argument('--path', '-path', metavar='path', \
	default=os.path.join(expanduser('~'),'Research', 'Protien_Database', \
		'extracted_new_samples', 'testing'), \
	help='Directory of input sample and other files.')
parser.add_argument('--keys', '-keys', metavar='keys', \
	default='6362130,6362129,6362128,6362131,6362132',\
	help='Key that is to be searched.')
parser.add_argument('--aacds', '-aacds', metavar='aacds', \
	default='gly,thr,lys',\
	help='Amino acids that are to be searched.')
parser.add_argument('--setting', '-setting', metavar='setting', \
	default='theta29_dist35', \
	help='Setting with theta and distance bin values.')
parser.add_argument('--exclude', '-exclude', metavar='exclude', \
	default=True, \
	help='Exclude certain keys from when extracting triplets details.')
parser.add_argument('--search_mode', '-search_mode', metavar='search_mode', \
	default=2, \
	help='0 if Key search, 2 if amino acid search and 3 if sequence identification.')
parser.add_argument('--identifying_pattern', '-identifying_pattern', \
	metavar='identifying_pattern', \
	default='ploop', \
	help='pllop if ploop, leu1 if lxxll and leu2 if llxxl.')
parser.add_argument('--low_freq', '-low_freq', metavar='low_freq', \
	default=1, \
	help='Keys with frequencies less than this number are considered.')
parser.add_argument('--dist_less', '-dist_less', metavar='dist_less', \
	default=12, \
	help='Keys with maxDist less than this number are considered.')

def search_by_key(fileName, file, keys, iskeys_file):
	print(fileName)
	search_records = []
	if iskeys_file == 1:
		line_count = len(file)
		df = file[file['key'].isin(keys)]

	else:
		line_count = 0
		for line in file:
			line_count += 1
			line_splitted=line.split('\t')
			if line_splitted[0].strip() in keys:
				search_records.append(line_splitted)	
		df = pd.DataFrame(search_records,columns = column_names)
	df.to_csv(os.path.join(args.path, args.sample_name, args.setting,'common_keys', \
				fileName +'_key_search_common_keys.csv'))		
	return (fileName, line_count, len(set(df['key'].values)), len(df['key'].values))
	

def search_aacd(file,aacds, req_pos):
	search_records = []	
	pattern_line = []
	for line in file:
		line_aacds = {}
		line_splitted=line.split('\t')
		line_aacd_arr = [line_splitted[1].strip().upper(), \
			line_splitted[3].strip().upper(), line_splitted[5].strip().upper()]	
		if sorted(line_aacd_arr) == sorted(aacds):
			search_records.append(line_splitted)
			if req_pos:
				line_pos_arr = [line_splitted[2].strip().upper(), \
					line_splitted[4].strip().upper(), \
					line_splitted[6].strip().upper()]
				if all(elem in req_pos for elem in line_pos_arr):
					pattern_line.append(line)
			
	return pd.DataFrame(search_records,columns = column_names), pattern_line

def identify_pattern_by_regex(files,column_names, patterns):
	matched = []
	all_pattern = generate_sequences_from_triplets_by_FR(file)
	for pattern in patterns:
		print(re.findall(pattern, all_pattern))
		matched.append(pattern)
	return ntpath.basename(file)[:4], matched

def identify_pattern_by_normal(file, pattern,count_of_x, group):
	matched = []
	# If file size is greater than 5 GB pandas is throwing Memory error
	# But if you always read line-by-line it is very slow. 
	# Hence using two way reading
	if float(os.path.getsize(file)/ 2**30) > 4 :
		print('File Size too big')
		return ntpath.basename(file)[:4], ['File Size too big']
		#all_pattern = generate_sequences_from_triplets_by_FR(file)	
	#all_pattern = generate_sequences_from_triplets_by_DF(file)
	all_pattern = generate_sequences_from_triplets_by_FR(file)	
	i = 0
	while i < len(all_pattern):
		if (all_pattern[i].split('_')[0] == pattern[0]) and ( i + count_of_x + len(pattern) < len(all_pattern)):
			#print('checking this: {}'.format(all_pattern[i:i + count_of_x + len(pattern)]))
			if group == 'ploop':
				if (all_pattern[i + count_of_x +1].split('_')[0] == pattern[1]) \
					and (all_pattern[i+count_of_x +2].split('_')[0] == pattern[2]) \
					and (all_pattern[i+count_of_x +3].split('_')[0] == pattern[3]):
					print( 'found', all_pattern[i:i + count_of_x + len(pattern)])
					matched.append(all_pattern[i:i + count_of_x + len(pattern)])
			if group == 'leu1':
				if (all_pattern[i + count_of_x +1].split('_')[0] == pattern[1]) \
					and (all_pattern[i+count_of_x +2].split('_')[0] == pattern[2]):
					print( 'found', all_pattern[i:i + count_of_x + len(pattern)])
					matched.append(all_pattern[i:i + count_of_x + len(pattern)])
			if group == 'leu2':
				if (all_pattern[i + 1].split('_')[0] == pattern[1]) \
					and (all_pattern[i+count_of_x +2].split('_')[0] == pattern[2]):
					print( 'found', all_pattern[i:i + count_of_x + len(pattern)])
					matched.append(all_pattern[i:i + count_of_x + len(pattern)])

		i += 1
	return (ntpath.basename(file)[:4], matched)

def generate_sequences_from_triplets_by_DF(file):
	print(ntpath.basename(file)[:4])
	all_pattern = []
	df = pd.read_table(file, delimiter = '\t', names = column_names)
	a_0 = pd.Series(df.aa0.values,index=df.pos0).to_dict()
	a_1 = pd.Series(df.aa1.values,index=df.pos1).to_dict()
	a_2 = pd.Series(df.aa2.values,index=df.pos2).to_dict()
	a_0.update(a_1) 
	a_0.update(a_2) 
	pos_aa_dict = sorted(a_0.items())
	for key, value in pos_aa_dict:
		all_pattern .append(str(value) + '_' + str(key))
	return all_pattern

def generate_sequences_from_triplets_by_FR(file):
	print( ntpath.basename(file)[:4])
	all_pattern = []
	pos_aa = {}
	for line in open(file,'r'):
		line_splitted=line.split('\t')
		if line_splitted[2].strip() not in pos_aa.keys():
			pos_aa[int(line_splitted[2].strip())] = line_splitted[1].strip().upper()
		if line_splitted[4].strip() not in pos_aa.keys():
			pos_aa[int(line_splitted[4].strip())] = line_splitted[3].strip().upper()
		if line_splitted[6].strip() not in pos_aa.keys():
			pos_aa[int(line_splitted[6].strip())] = line_splitted[5].strip().upper()
	for key, value in sorted(pos_aa.items()):
		all_pattern .append(str(value) + '_' + str(key))
	return all_pattern

def common_keys(files):
	print( 'Common Keys Calculation started.')
	common_keys = []
	start = time.time()
	print files
	for file in files:
		print( ntpath.basename(file)[:4])
		keys = []
		for line in open(file, 'r'):
			keys.append(line.split('\t')[0])
		if common_keys:
			common_keys = list(set(common_keys) & set(keys))
		else:
			common_keys = list(set(keys))
		
	print( 'Time taken for Common Keys Calculation: ', (time.time() - start)/60)
	return common_keys

def calculate_low_less15_freq_from_common_keys(outFolder, req_low_freq, req_max_dist):
	
	writer = pd.ExcelWriter(os.path.join(outFolder,\
		'all_common_key_distribution.xlsx'), \
		engine='xlsxwriter')
	writer_low_freq = pd.ExcelWriter(os.path.join(outFolder,\
		'only_low_freq{}_key_distribution.xlsx'.format(req_low_freq)), \
		engine='xlsxwriter')
	writer_dist_less15 = pd.ExcelWriter(os.path.join(outFolder,\
		'freq_less{}_dist_less{}_triplets.xlsx'.\
		format(str(req_low_freq), str(req_max_dist))), engine='xlsxwriter')
	summary = []
	commom_key_freqs = Counter()
	common_keys_files = glob.glob(os.path.join(outFolder, \
		'*_key_search_common_keys.csv'))
	for file in common_keys_files:
		print( ntpath.basename(file)[:4])
		df = pd.read_csv(file, delimiter = ',')
		x = Counter(df['key'].values)
		ckeys_freqs_df = pd.DataFrame(sorted(x.items(), key=lambda pair: pair[1], \
			 reverse=True), columns = ['key', 'freq'])
		ckeys_freqs_df.to_excel(writer,sheet_name=ntpath.basename(file)[:4])
		#Low Frequency Common Keys
		low_freqs = ckeys_freqs_df[ckeys_freqs_df['freq'] <= req_low_freq]
		low_freqs.to_excel(writer_low_freq,sheet_name=ntpath.basename(file)[:4])
		df_low_freqs_triplets = df[ df['key'].isin(set(low_freqs['key'].values))]
		#Distance less than 15
		df_distance_less15 = df_low_freqs_triplets[df_low_freqs_triplets['distance'] <= req_max_dist]
		df_distance_less15.to_excel(writer_dist_less15,sheet_name=ntpath.basename(file)[:4])
		summary.append((ntpath.basename(file)[:4], len(set(df_low_freqs_triplets['key'].values)),len(df_low_freqs_triplets['key'].values), \
			len(set(df_distance_less15['key'].values)), len(df_distance_less15)))
		print (ntpath.basename(file)[:4], len(set(df_low_freqs_triplets['key'].values)),len(df_low_freqs_triplets['key'].values), \
			len(set(df_distance_less15['key'].values)), len(df_distance_less15['key']))
		#Overall Common Keys
		if commom_key_freqs:
			commom_key_freqs = commom_key_freqs + x
		else:
			commom_key_freqs = x

	pd.DataFrame(sorted(commom_key_freqs.items(), key=lambda pair: pair[1], reverse=True)). \
		to_excel(writer,sheet_name='Summary')

	df_merge = pd.read_csv(os.path.join(outFolder, \
		'summary_common_keys.csv')).merge(pd.DataFrame(summary, \
			columns = ['fileName', '# of low freq common keys', \
			'# of low freq common keys(with freq)',\
			'# of low freq common keys with maxdist <= {}'.format(str(req_max_dist)), \
			'# of low freq common keys with maxdist <= {}(with freq)'.format(str(req_max_dist))]),\
		on = 'fileName')
	df_merge.to_csv(os.path.join(outFolder, 'summary_common_keys_merged.csv'))
	writer.close()
	writer_low_freq.close()
	writer_dist_less15.close()

def get_common_keys_groups():
	writer = pd.ExcelWriter(os.path.join(args.path, args.sample_name, \
					args.setting, 'common_keys_group_specific.xlsx'), \
					engine = 'xlsxwriter')
	samples_file = pd.read_csv(os.path.join(args.path, \
		args.sample_name, 'sample_details.csv'))
	groups = samples_file['group'].values
	files = glob.glob(os.path.join(args.path, args.sample_name, args.setting, '*.keys*'))
	all_common = common_keys(files)
	pd.DataFrame(all_common, columns = ['key'])\
						.to_excel(writer,sheet_name='all_common_keys')
	samples_file['filename'] = os.path.join(args.path, args.sample_name, args.setting) + '//' +samples_file['protein'] + '.keys_' + args.setting
	summary = []
	for group in groups:
		group_files = samples_file[samples_file['group'] == group]['filename'].values
		group_common_keys = common_keys(group_files)
		only_group_keys = set(group_common_keys) - set(all_common)
		pd.DataFrame(list(only_group_keys), \
						columns = ['key'])\
						.to_excel(writer,sheet_name=group)
		summary.append((group, len(group_common_keys), len(only_group_keys)))
	pd.DataFrame(summary, columns = ['group', 'All keys in group', 'Only group keys without common'])\
						.to_excel(writer,sheet_name='summary')
	writer.close()

def process_files(file, req_aacds):
	print(ntpath.basename(file)[:4])
	pattern_theta_1 = ''
	pattern_dist_1 = ''
	pattern_theta_2 = ''
	pattern_dist_2 = ''
	
	samples_file = pd.read_csv(os.path.join(args.path, \
		args.sample_name, 'sample_details.csv'))
	#req_pos = re.findall(r'\d+', samples_file.set_index('protein').\
	#	loc[ntpath.basename(file)[:4],  'pattern'])
	req_pos = []
	records, patterns = search_aacd(open(file,'r'),req_aacds, req_pos)
	
	if patterns:
		# pattern_theta_1 = [pattern.split('\t')[8] for pattern in patterns]
		# pattern_dist_1 = [pattern.split('\t')[10] for pattern in patterns]
		pattern_theta_1 = patterns[0].split('\t')[8]
		pattern_dist_1 = patterns[0].split('\t')[10]
		if len(patterns) >1:
			pattern_theta_2 = patterns[1].split('\t')[8]	
			pattern_dist_2 = patterns[1].split('\t')[10]
	records.to_csv(os.path.join(args.path, args.sample_name, \
			args.setting, 'common_keys', \
	 		ntpath.basename(file)[:4] + '_'+ "_".join(req_aacds) + '.csv'))
	print (ntpath.basename(file)[:4], pd.to_numeric(records['theta']).mean(),\
	 pd.to_numeric(records['distance']).mean(), pattern_theta_1, pattern_theta_2,\
	 pattern_dist_1, pattern_dist_2, patterns)
	return (ntpath.basename(file)[:4], pd.to_numeric(records['theta']).mean(),\
	 pd.to_numeric(records['distance']).mean(), pattern_theta_1, pattern_theta_2,\
	 pattern_dist_1, pattern_dist_2, patterns)

if __name__ == '__main__':
	start = time.time()
	args = parser.parse_args()
	files = glob.glob(os.path.join(args.path,\
					 args.sample_name, args.setting, '*.triplets*'))
	column_names = ['key', 'aa0', 'pos0', 'aa1', 'pos1', 'aa2', 'pos2', \
	'classT', 'theta', 'classL', 'distance', 'x0', 'y0', 'z0', 'x1', 'y1',\
	 'z1', 'x2', 'y2', 'z2']

	print(args.path, args.sample_name, args.setting)
	
	keys_files = glob.glob(os.path.join(args.path, args.sample_name, args.setting, '*.keys*'))

	outFolder = os.path.join(args.path, args.sample_name, args.setting, \
		'common_keys')
	print(outFolder)
	if not os.path.exists(outFolder):
		os.makedirs(outFolder) 
	
	# #Keys Search   
	if args.search_mode == 0:
		iskeys_file = 1
		summary = []
		#Either use list of keys given in args or use common keys
		#keys = [ str(key) for key in args.keys.split(',')]	
		#Common Keys
		keys = common_keys(files)
		
		#keys = pd.read_csv(os.path.join(outFolder,'common_keys.csv'), header = 0, index_col = 0)['key'].values
		print('Total common keys are: {}'.format(len(keys)))
		for file in files:	    
			#If reading with pandas
			if iskeys_file == 1:
				df = pd.read_table(file, delimiter = '\t', names = column_names)
				summary.append(search_by_key(ntpath.basename(file)[:4], \
							df,\
							keys,1))
			#line by line file read
			else:
				summary.append(search_by_key(ntpath.basename(file)[:4],\
							open(file,'r'),\
							keys, 0))					
			
		pd.DataFrame(summary, \
			columns = ['fileName', 'all_keys', 'common_keys', 'common_keys_with_freq']) \
			.to_csv(os.path.join(outFolder,'summary_common_keys.csv'))

	if int(args.search_mode) == 1:
		calculate_low_less15_freq_from_common_keys(outFolder, int(args.low_freq), int(args.dist_less))
	print 'sarika'

	# #Amino Acids Search
	if args.search_mode == 2:
		#ploop
		#all_list = [['GLY', 'LYS','SER', 'GLY'], ['GLY', 'LYS','THR', 'GLY']]
		#lxxll
		#Change here Sarika
		all_list = [['HIS', 'HIS', 'GLU']]#[['LEU', 'LEU','LEU']]
		print 'sarika2'
		print all_list
		print files
		already_completed = []
		for lst in all_list:
			print('Identifying for : {}'.format(lst))
			for req_aacds in itertools.combinations(lst, 3):
				if sorted(req_aacds) not in already_completed:
					already_completed.append(sorted(req_aacds))
					print('Started AminoAcid serach for: {}'.format("_".join(req_aacds)))
					means_theta = []
					means_distance = []
					writer = pd.ExcelWriter(os.path.join(args.path, args.sample_name, \
						args.setting, 'means_' + "_".join(req_aacds) + '.xlsx'), \
						engine = 'xlsxwriter')
					
					means_theta_distance  = Parallel(n_jobs=cpu_count() - 1, verbose=10, \
						backend="multiprocessing", batch_size="auto")(\
						delayed(process_files)(file, req_aacds) for file in files)
					pd.DataFrame(means_theta_distance, \
						columns = ['file', 'all_theta_per_protein', \
								'all_dist_per_protein', 'motif_theta_1','motif_theta_2', \
								'motif_dist_1', 'motif_dist_2','motif'])\
						.to_excel(writer,sheet_name='means_theta_distance')
					writer.close()

	#Sequence Identification
	if args.search_mode == 3:
		writer_pattern = pd.ExcelWriter(os.path.join(args.path, args.sample_name, \
					args.setting, 'patterns_{}{}'.format(args.identifying_pattern, '.xlsx')), \
					engine = 'xlsxwriter')
		#ploop
		if args.identifying_pattern == 'ploop':
			patterns = [['GLY','GLY','LYS','SER'], ['GLY','GLY','LYS','THR']]
			no_of_xs = 4
		if (args.identifying_pattern == 'leu1') or (args.identifying_pattern == 'leu2'):
			patterns = [['LEU', 'LEU','LEU']]
			no_of_xs = 2
		for pattern in patterns:
			matched_list = []
			# sequences  = Parallel(n_jobs=cpu_count() - 1, verbose=10, \
			# 			backend="multiprocessing", batch_size="auto")(\
			# 			delayed(identify_sequence)(file, column_names, \
			#  	[r'GLY_\d+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+GLY_\d+LYS_\d+SER_\d+', \
			#  	r'GLY_\d+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+GLY_\d+LYS_\d+THR_\d+']) for file in files)
			# identify_sequence(files,column_names, \
			# 	[r'GLY_\d+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+GLY_\d+LYS_\d+SER_\d+', \
			# 	r'GLY_\d+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+[A-Z]{3}_[\d]+GLY_\d+LYS_\d+THR_\d+'])
			matched_list = Parallel(n_jobs=cpu_count() - 1, verbose=10, \
						backend="multiprocessing", batch_size="auto")(\
						delayed(identify_pattern_by_normal)(file,pattern, no_of_xs, args.identifying_pattern)\
						for file in files)
			# for file in files:
			# 	matched_list.append(identify_pattern_by_normal(file,pattern, no_of_xs))
			pd.DataFrame(matched_list, columns = ['file','pattern_matched'])\
				.to_excel(writer_pattern, sheet_name = "_".join(pattern))

	if args.search_mode == 4:
		get_common_keys_groups()

	end = time.time()
	print("Task Completed. Total time taken: {} mins".format((end - start)/60))	

	

	
        


