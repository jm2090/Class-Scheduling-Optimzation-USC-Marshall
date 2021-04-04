#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from gurobipy import Model, GRB
import pandas as pd
import numpy as np
import time
import itertools as it
from datetime import datetime, date

'''Function which takes in two input arguments:
    - inputFile: the path to the input data. (.xlsx format)
    - outputFile: the path to the output data. (.xlsx format)
    - weight1, weight2, weight3:  weight assigned to the three 
      evaluation metrics: average classroom utilization rate, 
      the number of professors who are allocated at least one back-to-back class 
      and the number of professors who have to work more than two days a week. 
      The weights can be any decimals between 0 and 1, with 1 indicating 
      the corresponding feature is very important and 0 as not important at all. 
      If the end user didn’t input any weights, then the software will by default 
      interpret weight1 = 1, weight2 = 1 and weight3 = 0.2. 
    The outputFile gives the optimal schdule for all classes as well as 
    a summary of schedule performance evaluation'''

'''The Following Coding is Composed of 2 Major Parts, Input Data
    Preperation and Gurobi Coding'''

def optimize(inputFile,outputFile,weight1=1,weight2=1,weight3=0.2):
    # PART 1 [INPUT DATA PREPERATION] 
    
    # 1.0 Create 2 dictionaries for undergraduate and graduate to query input speperately
    print('Preprocess Data Input')
    start_time = time.time()
    ug = {}
    g = {}
    level = ["ug","g"]
    leveldics = [ug,g]
    ug["level"] = "ug"
    g["level"] = "g"

    # 1.0 Read Input from the InputFile
    g["timeslots"]=pd.read_excel(inputFile,sheet_name='Timeslots_G',index_col=0)
    ug["timeslots"]=pd.read_excel(inputFile,sheet_name='Timeslots_UG',index_col=0)
    g["classrooms"]=pd.read_excel(inputFile,sheet_name='Classrooms_G',index_col=0)
    ug["classrooms"]=pd.read_excel(inputFile,sheet_name='Classrooms_UG',index_col=0)
    Classes=pd.read_excel(inputFile,sheet_name='Sections',index_col=0)
    
    # 1.1 Prepare Timeslots (T) and (A-G)
    # 1.1.1 Prepare Timeslots (T)
    ug["T"] = ug["timeslots"].index
    g["T"] = g["timeslots"].index
    
    # 1.1.2 Add a section (A-G) label for each timeslot
    ug["double-length"] =4 
    g["double-length"] =3 
    ug["single-length"] =2 
    g["single-length"] =1.5

    for leveldic in leveldics:
        tempT = leveldic["timeslots"]
        tempT["Timepart"] = "part"
        for slot in leveldic["timeslots"].index:
            day = tempT.loc[slot,"Day"]
            session = tempT.loc[slot,"Session"]
            start = tempT.loc[slot,"StartTime"]
            end = tempT.loc[slot,"EndTime"]
            duration = (datetime.combine(date.min, end)-datetime.combine(date.min, start)).total_seconds()/(60*60)
            if session == "Full Semester" and len(day) == 2:
                tempT.loc[slot,"Timepart"] = "A"
            elif session == "Full Semester" and duration ==leveldic["double-length"]:
                tempT.loc[slot,"Timepart"] = "B"
            elif session == "Full Semester" and duration ==leveldic["single-length"]:
                tempT.loc[slot,"Timepart"] = "C"
            elif session == "First Half" and duration == leveldic["single-length"]:
                tempT.loc[slot,"Timepart"] = "D"
            elif session == "Second Half" and duration == leveldic["single-length"]:
                tempT.loc[slot,"Timepart"] = "E"
            elif session == "First Half" and duration == leveldic["double-length"]:
                tempT.loc[slot,"Timepart"] = "F"
            elif session == "Second Half" and duration == leveldic["double-length"]:
                tempT.loc[slot,"Timepart"] = "G"
        leveldic["timeslots"] = tempT
    timeparts = ["A","B","C","D","E","F","G"]
    for leveldic in leveldics:
        for timepart in timeparts:
            temp = leveldic["timeslots"]
            leveldic[timepart] = list(temp.loc[temp.Timepart == timepart].index)
    
    # 1.2 Prepare Time Conflicts (O)
    # 1.2.1 Create within-level conflicts (i.e. conflicts either between ug and ug timeslots or g and g timeslots)
    for leveldic in leveldics:
        leveldic["conflicts"] = []
        tempcombos = list(it.combinations(leveldic["T"], 2))
        for combo in tempcombos:
            t1 = combo[0]
            t2 = combo[1]
            t1_start = leveldic["timeslots"].loc[t1,"StartTime"]
            t1_end = leveldic["timeslots"].loc[t1,"EndTime"]
            t2_start = leveldic["timeslots"].loc[t2,"StartTime"]
            t2_end = leveldic["timeslots"].loc[t2,"EndTime"]
            t1_day = leveldic["timeslots"].loc[t1,"Day"]
            t2_day = leveldic["timeslots"].loc[t2,"Day"]
            t1_time = leveldic["timeslots"].loc[t1,"Timeslots"]
            t2_time = leveldic["timeslots"].loc[t2,"Timeslots"]
            t1_session = leveldic["timeslots"].loc[t1,"Session"]
            t2_session = leveldic["timeslots"].loc[t2,"Session"]
            if \
            (t1_start == t2_start or t1_end == t2_end or \
             (t1_start > t2_start and t1_start < t2_end) or \
             (t2_start > t1_start and t2_start < t1_end) or \
             (t1_end > t2_start and t1_end < t2_end) or \
             (t2_end > t1_start and t2_end < t1_end)) and \
            (t1_day == t2_day or t1_day == t2_day[0] or t1_day == t2_day[-1] or t1_day[0] == t2_day or t1_day[-1] == t2_day) and \
            (t1_session == t2_session or\
             (t1_session == "Full Semester" and t2_session == "First Half")or\
             (t1_session == "Full Semester" and t2_session == "Second Half")or\
             (t1_session == "First Half" and t2_session == "Full Semester")or\
             (t1_session == "Second Half" and t2_session == "Full Semester")):
                leveldic["conflicts"].append([t1,t2,t1_time,t2_time,t1_day,t2_day,t1_session,t2_session])
        leveldic["conflicts"] = pd.DataFrame(leveldic["conflicts"])
        leveldic["conflicts"].columns = ["t1","t2","t1_time","t2_time","t1_day","t2_day","t1_session","t2_session"]
    ug["O"] = []
    g["O"] = []
    for leveldic in leveldics:
        tempframe = leveldic["conflicts"]
        for i in tempframe.index:
            t1 = tempframe.loc[i,"t1"]
            t2 = tempframe.loc[i,"t2"]
            templist = [t1,t2]
            leveldic["O"].append(templist)
    
    # 1.2.2 Create Cross-level Conflicts (conflicts between ug timeslots and g timeslots)
    gtemp = g["timeslots"].copy()
    ugtemp = ug["timeslots"].copy()
    conflict = []
    for ugindex in ugtemp.index:
        for gindex in gtemp.index:
            ug_start = ugtemp.loc[ugindex,"StartTime"]
            ug_end = ugtemp.loc[ugindex,"EndTime"]
            g_start = gtemp.loc[gindex,"StartTime"]
            g_end = gtemp.loc[gindex,"EndTime"]
            ug_day = ugtemp.loc[ugindex,"Day"]
            g_day = gtemp.loc[gindex,"Day"]
            ug_time = ugtemp.loc[ugindex,"Timeslots"]
            g_time = gtemp.loc[gindex,"Timeslots"]
            ug_session = ugtemp.loc[ugindex,"Session"]
            g_session = gtemp.loc[gindex,"Session"]
            if \
            (ug_start == g_start or ug_end == g_end or \
             (ug_start > g_start and ug_start < g_end) or \
             (g_start > ug_start and g_start < ug_end) or \
             (ug_end > g_start and ug_end < g_end) or \
             (g_end > ug_start and g_end < ug_end)) and \
            (ug_day == g_day or ug_day == g_day[0] or ug_day == g_day[-1] or ug_day[0] == g_day or ug_day[-1] == g_day) and \
            ((ug_session == g_session)or\
             (ug_session == "Full Semester" and g_session == "First Half")or\
             (ug_session == "Full Semester" and g_session == "Second Half")or\
             (ug_session == "First Half" and g_session == "Full Semester")or\
             (ug_session == "Second Half" and g_session == "Full Semester")):
                conflict.append([ugindex,gindex,ug_time,g_time,ug_session,g_session])
    cross_conflict =  pd.DataFrame(conflict, columns=["ugindex","gindex","ugtime","gtime","ugsession","gsession"])
    
    # 1.3 Prepare Consecutive Timeslots (M)
    # 1.3.1 Within-Lvel Consecutive Timeslots
    for leveldic in leveldics:
        leveldic["M"] = []
        tempcombos = list(it.combinations(leveldic["T"], 2))
        for combo in tempcombos:
            t1 = combo[0]
            t2 = combo[1]
            t1_start = leveldic["timeslots"].loc[t1,"StartTime"]
            t1_end = leveldic["timeslots"].loc[t1,"EndTime"]
            t2_start = leveldic["timeslots"].loc[t2,"StartTime"]
            t2_end = leveldic["timeslots"].loc[t2,"EndTime"]
            t1_day = leveldic["timeslots"].loc[t1,"Day"]
            t2_day = leveldic["timeslots"].loc[t2,"Day"]
            t1_time = leveldic["timeslots"].loc[t1,"Timeslots"]
            t2_time = leveldic["timeslots"].loc[t2,"Timeslots"]
            t1_session = leveldic["timeslots"].loc[t1,"Session"]
            t2_session = leveldic["timeslots"].loc[t2,"Session"]
            if \
            (t1_start == t2_end or t1_end == t2_start) and \
            (t1_day == t2_day or t1_day == t2_day[0] or t1_day == t2_day[-1] or t1_day[0] == t2_day or t1_day[-1] == t2_day) and \
            (t1_session == t2_session or\
             (t1_session == "Full Semester" and t2_session == "First Half")or\
             (t1_session == "Full Semester" and t2_session == "Second Half")or\
             (t1_session == "First Half" and t2_session == "Full Semester")or\
             (t1_session == "Second Half" and t2_session == "Full Semester")):
                leveldic["M"].append([t1,t2,t1_time,t2_time,t1_day,t2_day,t1_session,t2_session])
        leveldic["M"] = pd.DataFrame(leveldic["M"])
        leveldic["M"].columns = ["t1","t2","t1_time","t2_time","t1_day","t2_day","t1_session","t2_session"]
        leveldic["M"]["t1"] = leveldic["M"]["t1"].astype(str)
        leveldic["M"]["t2"] = leveldic["M"]["t2"].astype(str)
        leveldic["M"]["t1_t2"] = leveldic["M"]["t1"] + '-' + leveldic["M"]["t2"]

    # 1.3.2 Cross-Level Consecutive Timeslots
    ug_g_consecutive = []
    for ugindex in ugtemp.index:
        for gindex in gtemp.index:
            ug_start = ugtemp.loc[ugindex,"StartTime"]
            ug_end = ugtemp.loc[ugindex,"EndTime"]
            g_start = gtemp.loc[gindex,"StartTime"]
            g_end = gtemp.loc[gindex,"EndTime"]
            ug_day = ugtemp.loc[ugindex,"Day"]
            g_day = gtemp.loc[gindex,"Day"]
            ug_time = ugtemp.loc[ugindex,"Timeslots"]
            g_time = gtemp.loc[gindex,"Timeslots"]
            ug_session = ugtemp.loc[ugindex,"Session"]
            g_session = gtemp.loc[gindex,"Session"]
            duration_1 = datetime.combine(date.today(), ug_start) - datetime.combine(date.today(), g_end)
            duration_1 = duration_1.total_seconds()/60
            duration_2 = datetime.combine(date.today(), g_start) - datetime.combine(date.today(), ug_end)
            duration_2 = duration_2.total_seconds()/60
            if \
            ((duration_1 < 30 and duration_1>=0) or (duration_2 < 30 and duration_2>=0)) and \
            (ug_day == g_day or ug_day == g_day[0] or ug_day == g_day[-1] or ug_day[0] == g_day or ug_day[-1] == g_day) and \
            ((ug_session == g_session)or\
             (ug_session == "Full Semester" and g_session == "First Half")or\
             (ug_session == "Full Semester" and g_session == "Second Half")or\
             (ug_session == "First Half" and g_session == "Full Semester")or\
             (ug_session == "Second Half" and g_session == "Full Semester")):
                ug_g_consecutive.append([ugindex,gindex,ug_time,g_time,ug_session,g_session])
    ug_g_consecutive =  pd.DataFrame(ug_g_consecutive, columns=["ugindex","gindex","ugtime","gtime","ugsession","gsession"])
    
    # 1.4 Prepare Classes (I) and Classes Partitions (a/b/c/d)
    g["classes"] = Classes[Classes.level == "G"] 
    ug["classes"] = Classes[Classes.level == "UG"] 
    g["I"] = g["classes"].index
    ug["I"] = ug["classes"].index
    ug["db_unit"] = 4
    g["db_unit"] = 3
    for leveldic in leveldics:
        tempclass = leveldic["classes"]
        leveldic["a"] = tempclass.loc[tempclass.units == leveldic["db_unit"]].index
        leveldic["b"] = tempclass.loc[(tempclass.units != leveldic["db_unit"])&(tempclass.session == 0)].index
        leveldic["c"] = tempclass.loc[(tempclass.units != leveldic["db_unit"])&(tempclass.session == 1)].index
        leveldic["d"] = tempclass.loc[(tempclass.units != leveldic["db_unit"])&(tempclass.session == 2)].index
    
    # 1.5 Prepare Classrooms(J)
    g["J"]=g["classrooms"].index
    ug["J"]=ug["classrooms"].index
    
    # 1.6 Prepare Professors(K) and (𝐿𝑘)
    temp1 = list(Classes["first_instructor"].unique())
    temp2 = list(Classes["second_instructor"].unique())
    temp2.remove(np.nan)
    ug["K"] = np.unique(np.array(temp1+temp2))
    g["K"] = np.unique(np.array(temp1+temp2))
    ug["L_k"] = {}
    g["L_k"] = {}
    for leveldic in leveldics:
        for k in leveldic["K"]:
            tempframe = leveldic["classes"].reset_index()
            condition = (tempframe.first_instructor == k)|(tempframe.second_instructor == k)
            templist = tempframe.loc[condition,"section"].to_list()
            leveldic["L_k"][k] = templist
    
    # 1.7 Prepare Utilization Rate (𝑈𝑖𝑗), Capacity Fit (𝑧𝑖𝑗) and Total Number of Classes (N)
    for leveldic in leveldics:
        leveldic["U_ij"] = pd.DataFrame(0,columns = leveldic["J"], index = leveldic["I"])
        leveldic["Z_ij"] = pd.DataFrame(0,columns = leveldic["J"], index = leveldic["I"])
        tempclass = leveldic["classes"]
        temproom = leveldic["classrooms"]
        for section in leveldic["I"]:
            for room in leveldic["J"]:
                seats = tempclass.loc[section,"seats_offered"]
                capacity = temproom.loc[room,"Capacity"]
                if seats <= capacity:
                    leveldic["U_ij"].loc[section,room] = seats/capacity*100
                    leveldic["Z_ij"].loc[section,room] = 1
    N = ug["classes"].shape[0] + g["classes"].shape[0]
    
    # 1.8 Define Weekdays(𝑆); Prepare Timeslots Partitioned by Weekdays (𝑉𝑠)
    S =['M','T','W','H','F']
    weekdays=['M','T','W','H','F']
    for leveldic in leveldics:
        leveldic["V"] = {}
        for weekday in S:
            leveldic["V"][weekday]=[]
    for leveldic in leveldics:
        for weekday in S:
            temp = leveldic["timeslots"]
            for tempt in temp.index:
                matchweekday = ((temp.loc[tempt,'Day'] == weekday) or (temp.loc[tempt,'Day'] == weekday[0]) or\
                    (temp.loc[tempt,'Day'] == weekday[-1]) or (temp.loc[tempt,'Day'][0] == weekday) or\
                    (temp.loc[tempt,'Day'][-1] == weekday))
                if matchweekday:
                    leveldic["V"][weekday].append(tempt) 
    print('Data Preprocessing Finished --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))
    print('You input {} classes, {} undergraduate timeslots,{} graudate timeslots, {} undergraduate classrooms and {} graduate classrooms'.format(Classes.shape[0],ug["T"].shape[0],g["T"].shape[0],ug["J"].shape[0],g["J"].shape[0]))
    
    print('Optimization Starts')
    # PART 2 [Gurobi Coding]
    start_time_original = time.time()
    
    # 2.1 [Set Variables]
    start_time = time.time()
    mod=Model()
    for leveldic in leveldics:
        leveldic["X"] = mod.addVars(leveldic["I"],leveldic["J"],leveldic["T"],vtype=GRB.BINARY)
        leveldic["y"] = mod.addVars(leveldic["J"],leveldic["T"])
        leveldic["w"] = mod.addVars(leveldic["K"],leveldic["T"])
        leveldic["H"] = mod.addVars(leveldic["K"],leveldic["M"]["t1_t2"],vtype=GRB.BINARY)
    U = mod.addVar(lb = 0)
    r = mod.addVars(leveldic["K"],vtype=GRB.BINARY)
    R = mod.addVar(lb = 0)
    Q = mod.addVar(vtype=GRB.INTEGER, lb=0)
    Z = mod.addVars(leveldic["K"],S,vtype=GRB.BINARY)
    q = mod.addVars(leveldic["K"],vtype=GRB.BINARY)
    print('Set Variables --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.2 [Set the objective]
    start_time = time.time() 
    mod.setObjective(weight1*U-weight2*Q+weight3*R,sense=GRB.MAXIMIZE)

    # 2.3 [Define U in the objective Function]
    mod.addConstr(U == (sum(g["U_ij"].loc[i,j]*g["X"][i,j,t] for i in g["I"] for j in g["J"] for t in g["T"])+\
                        sum(ug["U_ij"].loc[i,j]*ug["X"][i,j,t] for i in ug["I"] for j in ug["J"] for t in ug["T"]))/N)
    print('Set Objective --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.4 [Add the constraints]
    # 2.4.1 [Constraint 1]
    start_time = time.time()
    for leveldic in leveldics:
        for i in leveldic["a"]:
            A_B = leveldic["A"] + leveldic["B"]
            mod.addConstr(sum(leveldic["X"][i,j,t] for j in leveldic["J"] for t in A_B) == 1)
        for i in leveldic["b"]:
            C = leveldic["C"]
            mod.addConstr(sum(leveldic["X"][i,j,t] for j in leveldic["J"] for t in C) == 1)
        for i in leveldic["c"]:
            D_F = leveldic["D"] + leveldic["F"]
            mod.addConstr(sum(leveldic["X"][i,j,t] for j in leveldic["J"] for t in D_F) == 1)
        for i in leveldic["d"]:  
            E_G = leveldic["E"] + leveldic["G"]
            mod.addConstr(sum(leveldic["X"][i,j,t] for j in leveldic["J"] for t in E_G) == 1)
        for i in leveldic["I"]:
            mod.addConstr(sum(leveldic["X"][i,j,t] for j in leveldic["J"] for t in leveldic["T"]) == 1)
    print('Set Constraint 1 --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.4.2 [Constraint 2]
    start_time = time.time()
    for leveldic in leveldics:
        for j in leveldic["J"]:
            for t in leveldic["T"]:
                mod.addConstr(sum(leveldic["X"][i,j,t] for i in leveldic["I"]) <= 1,name = f'Con2_{j}_{t}')
    for leveldic in leveldics:
        for j in leveldic["J"]:
            for t in leveldic["T"]:
                leveldic["y"][j,t] = sum(leveldic["X"][i,j,t] for i in leveldic["I"])
        for j in leveldic["J"]:
            for o in leveldic["O"]:
                mod.addConstr(leveldic["y"][j,o[0]]+leveldic["y"][j,o[1]]<=1)
    print('Set Constraint 2 --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.4.3 [Constraint 3]
    start_time = time.time()
    for leveldic in leveldics:
        for i in leveldic["I"]:
            for j in leveldic["J"]:
                mod.addConstr(sum(leveldic["X"][i,j,t] for t in leveldic["T"]) <= leveldic["Z_ij"].loc[i,j])
    print('Set Constraint 3 --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.4.4 [Constraint 4]
    start_time = time.time()
    # 2.4.4.1 When teaching either ug/g classes, oen professor can't be assigned to one timeslot in two different classrooms
    for leveldic in leveldics:
        for t in leveldic["T"]:
            for k in leveldic["K"]:
                mod.addConstr(sum(leveldic["X"][i,j,t] for i in leveldic["L_k"][k] for j in leveldic["J"])<= 1)

    # 2.4.4.2 When teaching either ug/g classes, oen professor can't be assigned to two overlapping timeslots
    for leveldic in leveldics:
        for k in leveldic["K"]:
            for t in leveldic["T"]:
                leveldic["w"][k,t] = sum(leveldic["X"][i,j,t] for i in leveldic["L_k"][k] for j in leveldic["J"])
        for k in leveldic["K"]:
            for o in leveldic["O"]:
                mod.addConstr(leveldic["w"][k,o[0]]+leveldic["w"][k,o[1]]<=1)

    # 2.4.4.3 When teaching both ug/g classes, one professor can't be assigned to two overlapping timeslots (Reconcile conflict between ug/g timeslots)
    tempcross = cross_conflict[["ugindex","gindex"]].values.tolist()
    totK = ug["K"] #ug["K"] == g["K"] == K
    for cross in tempcross:
        for k in totK:
            ugtime = cross[0]
            gtime = cross[1]
            mod.addConstr(sum(ug["X"][i,j,ugtime] for i in ug["L_k"][k] for j in ug["J"]) + 
                          sum(g["X"][i,j,gtime] for i in g["L_k"][k] for j in g["J"])<=1)
    print('Set Constraint 4 --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.4.5 [Constraint 5]
    start_time = time.time()
    for leveldic in leveldics:
        tempcon = leveldic["M"]
        for k in leveldic["K"]:
            for t1_t2 in tempcon["t1_t2"].to_list():
                t1 = int(tempcon.loc[tempcon.t1_t2 == t1_t2,"t1"].values[0])
                t2 = int(tempcon.loc[tempcon.t1_t2 == t1_t2,"t2"].values[0])
                middlepart = (sum(leveldic["X"][i,j,t1] for i in leveldic["L_k"][k] for j in leveldic["J"]) +\
                              sum(leveldic["X"][i,j,t2] for i in leveldic["L_k"][k] for j in leveldic["J"])+1)
                mod.addConstr(3*leveldic["H"][k,t1_t2] <= middlepart)
                mod.addConstr(middlepart <= N*leveldic["H"][k,t1_t2]+2)

    for k in leveldic["K"]:
        temp = (sum(ug["H"][k,t1_t2] for t1_t2 in ug["M"]["t1_t2"].to_list()) + \
                sum(g["H"][k,t1_t2] for t1_t2 in g["M"]["t1_t2"].to_list()))
        mod.addConstr(r[k] <= temp)
        mod.addConstr(temp <= N*r[k])

    mod.addConstr(sum(r[k] for k in ug["K"])== R)
    print('Set Constraint 5 --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.4.6 [Constraint 6]
    start_time = time.time()
    for k in leveldic["K"]:
        for s in S:
            tempug = sum(ug["X"][i,j,t] for i in ug["L_k"][k] for j in ug["J"] for t in ug["V"][s])
            tempg = sum(g["X"][i,j,t] for i in g["L_k"][k] for j in g["J"] for t in g["V"][s])
            mod.addConstr(tempug + tempg >=Z[k,s])
            mod.addConstr(tempug + tempg <=Z[k,s]*N)

    for k in leveldic["K"]:
        mod.addConstr(sum(Z[k,s] for s in S)>=3*q[k])
        mod.addConstr(sum(Z[k,s] for s in S)<=N*q[k]+2)

    mod.addConstr(sum(q[k] for k in ug["K"]) == Q)
    print('Set Constraint 6 --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.5 [Optimize]
    start_time = time.time()
    mod.setParam('OutputFlag',False) 
    mod.optimize()
    print('Optimize --> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))

    # 2.6 [Optimal solution]
    start_time = time.time()
    for leveldic in leveldics:
        leveldic["output"] = pd.DataFrame(index = leveldic["I"])
        for i in leveldic["I"]:
            for j in leveldic["J"]:
                for t in leveldic["T"]:
                    if leveldic["X"][i,j,t].x:
                        leveldic["output"].loc[i,"Course"] = leveldic["classes"].loc[i,"course"]
                        leveldic["output"].loc[i,"Classroom"] = j
                        leveldic["output"].loc[i,"Time"] = leveldic["timeslots"].loc[t,"Timeslots"]
                        leveldic["output"].loc[i,"Session"] = leveldic["timeslots"].loc[t,"Session"]
                        leveldic["output"].loc[i,"Day"] = leveldic["timeslots"].loc[t,"Day"]
                        leveldic["output"].loc[i,"StartTime"] = leveldic["timeslots"].loc[t,"StartTime"]
                        leveldic["output"].loc[i,"EndTime"] = leveldic["timeslots"].loc[t,"EndTime"]
                        leveldic["output"].loc[i,"Units"] = leveldic["classes"].loc[i,"units"]
                        leveldic["output"].loc[i,"Seats Offered"] = leveldic["classes"].loc[i,"seats_offered"]
                        leveldic["output"].loc[i,"Classroom Capacity"] = leveldic["classrooms"].loc[j,"Capacity"]
                        leveldic["output"].loc[i,"Utilization Rate"] = leveldic["U_ij"].loc[i,j]
                        leveldic["output"].loc[i,"First Instructor"] = leveldic["classes"].loc[i,"first_instructor"]
                        leveldic["output"].loc[i,"Second Instructor"] = leveldic["classes"].loc[i,"second_instructor"]
    summary = [[f"Objective","Scheduling Score, {}*U-{}*Q+{}*R".format(weight1,weight2,weight3),round(mod.objval,2)],
               ["U","Average Utilization Rate, in %",round(U.x,2)],
               ["R","# of professors with >=1 back-to-back class",round(R.x,0)],
               ["Q","# of professors has to work >2 days a week",Q.x]]
    summary = pd.DataFrame(summary)
    summary.columns = ["Variable","Desciption","Optimal Value"]
    writer=pd.ExcelWriter(outputFile)
    summary.to_excel(writer,sheet_name = 'Summary',index=0)
    ug["output"].to_excel(writer,sheet_name = 'Undergrad Schedule')
    g["output"].to_excel(writer,sheet_name = 'Grad Schedule')
    writer.save()
    print('Write Solution--> {:.1f} minutes elapsed'.format((time.time()-start_time)/60))
    print('Successfully Finished Optimization in {:.1f} minutes'.format((time.time()-start_time_original)/60))
    
if __name__=='__main__':
    import sys, os
    if len(sys.argv)!=3 and len(sys.argv)!=6:
        print('Correct syntax: python optimize.py inputFile outputFile weight1(optional) weight2(optional) weight3(optional)')
    else:
        inputFile=sys.argv[1]
        outputFile=sys.argv[2]
        if len(sys.argv)==6:
            weight1 = sys.argv[3]
            weight2 = sys.argv[4]
            weight3 = sys.argv[5]
        if os.path.exists(inputFile):
            optimize(inputFile,outputFile)
            print(f'Results in "{outputFile}"')
        else:
            print(f'File "{inputFile}" not found!')
