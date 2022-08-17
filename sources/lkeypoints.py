import os
import json
import copy
import math
from collections import deque        

import numpy as np
from tqdm import tqdm
import scipy.io as sio
from joblib import Parallel, delayed
import scipy.io

import lglobalvars
import lprimitives 

#############################################################################
# Helper functions for scaling and centering keypoints                      # 
#############################################################################
def get_scale(keypoints):
    upper_body_size = (-keypoints[0][0][1] + (keypoints[9][0][1] + keypoints[12][0][1]) / 2.0)
    rcalf_size = np.sqrt((keypoints[10][0][1] - keypoints[11][0][1]) ** 2 + (keypoints[10][0][0] - keypoints[11][0][0]) ** 2)
    lcalf_size = np.sqrt((keypoints[13][0][1] - keypoints[14][0][1]) ** 2 + (keypoints[13][0][0] - keypoints[14][0][0]) ** 2)
    calf_size = (lcalf_size + rcalf_size) / 2.0

    size = np.max([2.5 * upper_body_size, 5.0 * calf_size])
    return size / 400.0

def normalize_list(keypoint, center=None, scale=None):
    if center is None:
        center = lglobalvars.center
    if scale is None:
        scale = lglobalvars.scale
    res_keypoint = copy.deepcopy(keypoint)
    x_offset = (512 - 1.0) / 2.0 - \
                    center[0] * scale
    y_offset = (512 - 1.0) / 2.0 - \
                    center[1] * scale
    for idx, elem in enumerate(res_keypoint):
        res_keypoint[idx] = (res_keypoint[idx][0] * scale + x_offset,
                          res_keypoint[idx][1] * scale + y_offset)
    return res_keypoint

def normalize(keypoints, center=None, scale=None):
    if center is None:
        center = lglobalvars.center
    if scale is None:
        scale = lglobalvars.scale
    res_keypoints = copy.deepcopy(keypoints)
    for idx in res_keypoints:
        res_keypoints[idx] = normalize_list(res_keypoints[idx], center, scale)
    return res_keypoints

def unnormalize_list(keypoint, center=None, scale=None):
    if center is None:
        center = lglobalvars.center
    if scale is None:
        scale = lglobalvars.scale
    res_keypoint = copy.deepcopy(keypoint)
    x_offset = (512 - 1.0) / 2.0 - \
                    center[0] * scale
    y_offset = (512 - 1.0) / 2.0 - \
                    center[1] * scale
    for idx, elem in enumerate(res_keypoint):
        res_keypoint[idx] = (int((res_keypoint[idx][0] - x_offset) / scale),
                                int((res_keypoint[idx][1] - y_offset) / scale))
    return res_keypoint

def unnormalize(keypoints, center=None, scale=None):
    if center is None:
        center = lglobalvars.center
    if scale is None:
        scale = lglobalvars.scale
    res_keypoints = copy.deepcopy(keypoints)
    for idx in res_keypoints:
        res_keypoints[idx] = unnormalize_list(res_keypoints[idx], center, scale)
    return res_keypoints



#############################################################################
# Load function for popular pose detectors/body keypoints                   # 
#############################################################################
def load(data_path, pose_detector, pose_type="posewarp"):
    if pose_detector == "alphapose":
        vid_info = json.load(open(os.path.join(data_path, "alphapose-results-halpe26-posetrack.json"), "r"))
        # print (type(vid_info))
        def image_id(elem):
            return int(elem['image_id'].split('.')[0])
        vid_info = sorted(vid_info, key=image_id)

        idx_scores = {}
        for i, x in enumerate(vid_info):
            bbox_wgt = x['box'][2] * x['box'][3]
            if x['idx'] in idx_scores:
                idx_scores[x['idx']] += x['score'] * bbox_wgt
            else:
                idx_scores[x['idx']] = x['score'] * bbox_wgt

        max_idx = list(idx_scores.keys())[0]
        for elem in idx_scores:
            if idx_scores[elem] > idx_scores[max_idx]:
                max_idx = elem        

        info_filter = []
        for i, x in enumerate(vid_info):
            if x['idx'] == max_idx:
                info_filter.append(x)

        keypoints = {}

        if pose_type == 'coco':
            for joint in lglobalvars.coco_joints:
                keypoints[joint] = []
        
            for frame_num in range(len(info_filter)):
                joints_raw = np.array(info_filter[frame_num]['keypoints']).reshape(26, 3)[:, :2]
                joints = joints_raw[[0, 18, 6, 8, 10, 5, 7, 9, 12, 14, 16, 11, 13, 15, 2, 1, 4, 3]]
                for idx, joint in enumerate(lglobalvars.coco_joints):
                    keypoints[joint].append(joints[idx])
        
        elif pose_type == 'posewarp':
            for joint in lglobalvars.posewarp_joints:
                keypoints[joint] = []

            for frame_num in range(len(info_filter)):
                joints_raw = np.array(info_filter[frame_num]['keypoints']).reshape(26, 3)[:, :2]
                joints = joints_raw[[17, 18, 5, 7, 9, 6, 8, 10, 11, 13, 15, 12, 14, 16]]
                for idx, joint in enumerate(lglobalvars.posewarp_joints):
                    keypoints[joint].append(joints[idx]) 
        
        elif pose_type == 'mpii':
            for joint in lglobalvars.mpii_joints:
                keypoints[joint] = []

            for frame_num in range(len(info_filter)):
                joints_raw = np.array(info_filter[frame_num]['keypoints']).reshape(26, 3)[:, :2]
                joints = joints_raw[[17, 18, 5, 7, 9, 6, 8, 10, 19, 11, 13, 15, 12, 14, 16]]
                for idx, joint in enumerate(lglobalvars.mpii_joints):
                    keypoints[joint].append(joints[idx]) 
        
        return keypoints
    
def load_from_data_cube(cube_path):
    
    mat = scipy.io.loadmat(cube_path)
    nb_frame = len(mat["data"][0,:,0])
    nb_joints = len(mat["data"][0,0,:])
    
    keypoints = {}
    for i in range(nb_joints):
        keypoints[i] = []
        for j in range(nb_frame): 
            keypoints[i].append([mat["data"][0,j,i] , mat["data"][1,j,i]])
            
    return keypoints

def load_from_data_cube_wrt_y(cube_path):
    
    mat = scipy.io.loadmat(cube_path)
    nb_frame = len(mat["data"][0,:,0])
    nb_joints = len(mat["data"][0,0,:])
    time = np.linspace(0, nb_frame-1, nb_frame)
    
    keypoints = {}
    for i in range(nb_joints):
        keypoints[i] = []
        for j in range(nb_frame): 
            keypoints[i].append([time[j], mat["data"][1,j,i]])
            
    return keypoints

def load_synthetic_signals(signal, time):
    
    keypoints = {}
    keypoints[0] = []
    nb_frames = len(signal)
    
    for i in range(nb_frames): 
        keypoints[0].append([time[i], signal[i]])
    
    return keypoints
    
    
#############################################################################
# Approximate missing keypoints                                             # 
#############################################################################
def fix_failed(keypoints):
    for idx in keypoints:
        for jdx, elem in enumerate(keypoints[idx]):
            if elem[0] == 0 and elem[1] == 0:
                if jdx != 0:
                    keypoints[idx][jdx] = keypoints[idx][jdx - 1]
                else:
                    kdx = 1
                    while keypoints[idx][kdx][0] == 0 and keypoints[idx][kdx][1] == 0:
                        kdx += 1
                    keypoints[idx][0] = keypoints[idx][kdx]
    return keypoints

#############################################################################
# Fit best primitive to a set of keypoints                                  # 
#############################################################################
def fit_primitive(keypoint, synt_args):
    
    # stat_thres: Points lying inside square of this edge length will be marked stationary
    # span_thres: If primitive start/end points are closer than this, then label it stationary
    # r_penalty: Add radius penalty for large/small circles
    # no_acc: 'Do not use acceleration term for primitives
    stat_thres = synt_args['stat_thres']
    span_thres = synt_args['span_thres']
    no_acc = synt_args['no_acc']
    r_penalty = synt_args['r_penalty']
    
    joint_prim = {}
    global_error = 0
    
    # 1st test : is it stationary ?
    x_s, y_s, s_error = lprimitives.stationary_fit(keypoint, algorithm="mean")
    if lprimitives.is_localized(keypoint, stat_thres):
        joint_prim[0] = ((x_s, y_s), len(keypoint), "STATIONARY")
        global_error = s_error
        return joint_prim, global_error
        
    # 2nd test : is it linear ?
    if no_acc:
        x_eq, y_eq, line_error, span_error = lprimitives.linear_fit_noacc(keypoint)
    else:
        x_eq, y_eq, line_error, span_error = lprimitives.linear_fit(keypoint)
    if span_error < span_thres:
        line_error = s_error + 1

    # 3rd test : is it circular ?
    circle_flag = False
    if not lprimitives.is_collinear(keypoint):
        if no_acc:
            x_c, y_c, r, ang_eq, circle_error, span_error = lprimitives.circle_fit_noacc(keypoint)
        else:
            x_c, y_c, r, ang_eq, circle_error, span_error = lprimitives.circle_fit(keypoint)
        if r_penalty:
            circle_error += max(r - 100, 0) * 3
            if r < 30:
                circle_error += r * 3
        if span_error < span_thres:
            circle_error = s_error + 1
        circle_flag = True

    x1, y1 = keypoint[0][0], keypoint[0][1]
    x2, y2 = keypoint[-1][0], keypoint[-1][1]

    # Select motion primitive based on minimal error 
    if circle_flag:
        min_error = min(s_error, line_error, circle_error)
        if min_error >= s_error or s_error / len(keypoint) < 3:
            joint_prim[0] = ((x_s, y_s), len(keypoint), "STATIONARY")
            global_error = s_error
        elif circle_error >= line_error:
            joint_prim[0] = ((x1, y1), (x2, y2), x_eq.tolist(), y_eq.tolist(), len(keypoint), "LINE")
            global_error = line_error
        else:
            joint_prim[0] = ((x1, y1), (x2, y2), (x_c, y_c), r, ang_eq.tolist(), len(keypoint), "CIRCLE")
            global_error = circle_error
    else:
        min_error = min(s_error, line_error)
        if min_error >= s_error or s_error / len(keypoint) < 3:
            joint_prim[0] = ((x_s, y_s), len(keypoint), "STATIONARY")
            global_error = s_error
        else:
            joint_prim[0] = ((x1, y1), (x2, y2), x_eq.tolist(), y_eq.tolist(), len(keypoint), "LINE")
            global_error = line_error

    return joint_prim, global_error

#############################################################################
# Segmentation algorithm                                                    # 
#############################################################################

def wrapper_fit_primitive(i, keypoints, synt_args):
    result = {}
    points_pp = synt_args['points_pp']
    window = synt_args['window']
    for j in range(max(0, i - window), i):
        result[j] = {}
        for joint in keypoints.keys():
            result[j][joint] = fit_primitive(keypoints[joint][(j - max(0, i - window))*points_pp:], synt_args)
    return result


def generate_all_primitives(keypoints, type_fit, synt_args):
    # REG : Regularization term to be used in DP (use -1 to infer automatically)
    # points_pp : Search only for primitive lengths in multiples of points_pp (reduces search space)
    # window : Window around which primitive is searched (i.e. max prim len = points_pp * window) (prefers even number)

    points_pp = synt_args['points_pp']
    REG = synt_args['REG']
    cores = synt_args['cores']
    window = synt_args['window']
    
    nb_frames = len(keypoints[0])
    
    # Decompose each keypoint trajectory into a sequence of primitives 
    if type_fit == "dp_all":
        pieces = math.ceil(nb_frames / points_pp)

        # fill initial entries of the DP table
        # table idx i has best fit for first (i + 1) pieces
        zero_prims, one_prims, one_error = {}, {}, 0
        for joint in keypoints.keys():
            zero_prims[joint] = {}
            first_prim, first_error = fit_primitive(keypoints[joint][:points_pp], synt_args)
            one_error += first_error
            one_prims[joint] = first_prim

        # function to extract smaller windows of keypoints
        def smaller_kp(keypoints, i, window, pos='left'):
            new_keypoints = {}
            for joint in keypoints.keys():
                if pos == 'left':
                    new_keypoints[joint] = keypoints[joint][max(0, i - window)*points_pp:i*points_pp]
                else:
                    max_len = len(keypoints[joint])
                    new_keypoints[joint] = keypoints[joint][max(0, i - window // 2)*points_pp:min((i + window // 2)*points_pp, max_len)]
            return new_keypoints

        # fit primitives
        pre_computation = Parallel(n_jobs=cores, backend='multiprocessing')\
                            (delayed(wrapper_fit_primitive)(i, smaller_kp(keypoints, i, window), \
                            synt_args) for i in tqdm(range(2, pieces + 1)))

        # precompute regularization values if using adaptive reg
        def variance_kp(keypoint):
            curr_std = np.cov(np.asarray(keypoint).T)
            return np.linalg.norm(curr_std)

        if REG == -1:
            print("[info] regularization: REG set to -1, using adaptive reg...")
            tvars, mvars = {}, {}
            for i in tqdm(range(1, pieces + 1)):
                curr_kps = smaller_kp(keypoints, i, window, pos='mid')
                curr_tvar, curr_mvar = 0, 0
                for joint in curr_kps.keys():
                    curr_var = variance_kp(curr_kps[joint])
                    curr_tvar, curr_mvar = curr_tvar + curr_var, max(curr_mvar, curr_var)
                tvars[i] = curr_tvar
                mvars[i] = curr_mvar
        else:
            print(f"[info] regularization: REG set to {REG}, using fixed reg...")
        
        # regularization mapping, upper bound & lower bound it
        def reg_map(num):
            if num / 2 > 1600:
                return 1600
            elif num / 2 < 200:
                if num / 3 < 100:
                    return 100
                else:
                    return num / 3
            else:
                return num / 2

        # main dp loop
        dp_table = deque()
        dp_table.append((0, 0, [], [], [], zero_prims))
        if REG == -1:
            dp_table.append((one_error + reg_map(tvars[1]), 1, [reg_map(tvars[1])], one_prims))
        else:
            dp_table.append((one_error + REG, 1, [REG], one_prims))
        
        for i in tqdm(range(2, pieces + 1)):
            min_error = math.inf
            min_j = None
            min_prim = None
            for j in range(max(0, i - window), i):
                curr_prim = {}
                curr_tvar, curr_mvar = 0, 0 
                curr_error = dp_table[j - max(0, i - window)][0]
                for joint in keypoints.keys():
                    joint_prim, prim_error = pre_computation[i - 2][j][joint]
                    curr_error += prim_error
                    curr_prim[joint] = joint_prim
                if curr_error < min_error:
                    min_error = curr_error
                    min_j = j
                    min_prim = curr_prim

            curr_prims = {}
            for joint in keypoints.keys():
                curr_prims[joint] = copy.deepcopy(dp_table[min_j - max(0, i - window)][-1][joint])
                curr_prims[joint][len(curr_prims[joint])] = min_prim[joint][0]
                curr_prim_len = dp_table[min_j - max(0, i - window)][1]

            curr_prim_regvar = copy.deepcopy(dp_table[min_j - max(0, i - window)][2])
            if REG == -1:
                curr_prim_regvar.append(reg_map(tvars[i]))
                dp_table.append((min_error + reg_map(tvars[i]), curr_prim_len + 1, curr_prim_regvar, curr_prims))
            else:
                curr_prim_regvar.append(REG)
                dp_table.append((min_error + REG, curr_prim_len + 1, curr_prim_regvar, curr_prims))
            
            if len(dp_table) > window:
                dp_table.popleft()
        
        print(f"[info] Done synthesis! Found total of {dp_table[-1][1]} primitives!")
        print(f'[info] Total error w.r.t. ground truth = {dp_table[-1][0]}')
        return dp_table[-1][-1]

    # If we need a single primitive per keypoint which is never the case
    elif type_fit == "single_primitive":
        nb_keypoints = len(keypoints)
        all_prim = {}
        for joint in range(nb_keypoints):
            keypoint = copy.deepcopy(keypoints[joint])
            joint_prim, _ = fit_primitive(keypoint, synt_args)
            all_prim[joint] = joint_prim
        return all_prim
    
    
#############################################################################
# Execute a single primitive to get keypoints (viz purposes)                #
#############################################################################
def trace_prim(prim, prune_acc=False, noacc_t=None):
    keypoints = []
    t = prim[-2]
    if prim[-1] == "LINE":
        px = np.poly1d(prim[2])
        py = np.poly1d(prim[3])
        for i in range(t):
            if prune_acc and i == noacc_t:
                px = np.poly1d(prune_acc_func(prim[2], noacc_t))
                py = np.poly1d(prune_acc_func(prim[3], noacc_t))
            new_x = px(i)
            new_y = py(i)
            keypoints.append((int(round(new_x)), int(round(new_y))))
    elif prim[-1] == "CIRCLE":
        cx, cy = prim[2]
        r = prim[3]
        p = np.poly1d(prim[4])
        for i in range(t):
            if prune_acc and i == noacc_t:
                p = np.poly1d(prune_acc_func(prim[4], noacc_t))
            angle = p(i)
            new_x = cx + r * np.cos(angle * np.pi / 180)
            new_y = cy + r * np.sin(angle * np.pi / 180)
            keypoints.append((int(round(new_x)), int(round(new_y))))
    else:
        for i in range(t):
            keypoints.append((int(round(prim[0][0])), int(round(prim[0][1]))))
    return keypoints


#############################################################################
# Execute a sequence of primitives to get keypoints (viz purposes)          # 
#############################################################################
def trace_funky_primitives(all_prim, intplt_f=1):
    keypoints = {}
    color_code, color_codes = 0, []
    for joint in all_prim.keys():
        keypoints[joint] = []
        joint_prim = all_prim[joint]
        for prim_idx in joint_prim:
            prim = joint_prim[prim_idx]

            if prim[-1] == "LINE":
                px = np.poly1d(prim[2])
                py = np.poly1d(prim[3])
                gen_length = prim[4]
                for i in range(gen_length):
                    stretch_to = intplt_f if i != gen_length - 1 else 1
                    for j in range(stretch_to):
                        new_x = px(i + j / intplt_f)
                        new_y = py(i + j / intplt_f)
                        curr_xy = (int(round(new_x)), int(round(new_y)))
                        keypoints[joint].append(curr_xy)
                        if joint == 0:
                            color_codes.append(color_code)

            elif prim[-1] == "CIRCLE":
                cx, cy = prim[2]
                r = prim[3]
                p = np.poly1d(prim[4])
                gen_length = prim[5]
                for i in range(gen_length):
                    stretch_to = intplt_f if i != gen_length - 1 else 1
                    for j in range(stretch_to):
                        angle = p(i + j / intplt_f)
                        new_x = cx + r * np.cos(angle * np.pi / 180)
                        new_y = cy + r * np.sin(angle * np.pi / 180)
                        curr_xy = (int(round(new_x)), int(round(new_y)))
                        keypoints[joint].append(curr_xy)
                        if joint == 0:
                            color_codes.append(color_code)

            elif prim[-1] == "STATIONARY":
                gen_length = prim[1]
                for i in range(gen_length):
                    stretch_to = intplt_f if i != gen_length - 1 else 1
                    for j in range(stretch_to):
                        curr_xy = (int(round(prim[0][0])), int(round(prim[0][1])))
                        keypoints[joint].append(curr_xy)
                        if joint == 0:
                            color_codes.append(color_code)
            
            else :
                print('ERROR YOU DUMB FUCK')
            color_code = 1 - color_code

    return keypoints, color_codes
