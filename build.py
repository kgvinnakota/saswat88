import os
import json
import glob

class ActionParams():
    def __init__(self):
        self.registry = {'refer': {}, 'load': {}}

        # maya standard types
        self.register('refer', '.ma', r=True, type="mayaAscii")
        self.register('refer', '.mb', r=True, type="mayaBinary")
        self.register('refer', '.abc', r=True, type="Alembic")

        self.register('load', '.abc', i=True, type="Alembic")
        self.register('load', '.ma', pr=True,i=True, type="mayaAscii")
        self.register('load', '.mb',pr=True, i=True, type="mayaBinary")

    def register(self, action_type, extension, **kwargs):
        self.registry[action_type][extension] = kwargs

class Path(ActionParams):
    def __init__(self):
        ActionParams.__init__(self)
        self.keys = ['file_name', 'process', 'asset_name', 'asset_type', 'show', 'repo']
        self.args = []
        self.kwargs = {x: '*' for x in self.keys}
        self.data_sets = {}
        self.sources = {}
        self.shotgun_data = {}
        self.data_set_groups = {}
        self.exclude_list = []

    def generate(self,type):
        if type in self.kwargs.keys():
            self.kwargs['repo']=self.kwargs[type]
        if 'variant' in self.kwargs:
            return '{repo}/{show}/{asset_type}/{asset_name}/{process}/{process_code}_{show}_{asset_type_code}_{asset_name}__{variant}.{extension}'.format(
                **self.kwargs)
        else:
            return '{repo}/{show}/{asset_type}/{asset_name}/{process}/{process_code}_{show}_{asset_type_code}_{asset_name}.{extension}'.format(
                **self.kwargs)

class Data(Path):
    def __init__(self, **kwargs):
        Path.__init__(self)
        self.kwargs.update({'meta': 'M:', 'live': 'L:', 'work': 'W:','process_code':'*','asset_type_code':'*','extension':'*'})
        if 'file_path' in kwargs:
            # file_path found in kwargs split the path and generate the keys
            self.args = kwargs['file_path'].split('/')
            if self.args[-1].split('.')[0] in self.args:
                self.args.remove(self.args[-2])

            self.kwargs['process_code'] = self.args[-1].split('_')[0]
            self.kwargs['asset_type_code'] = self.args[-1].split('_')[2]
            if '__' in self.args[-1]:
                self.kwargs['variant']=self.args[-1].split('__',1)[-1].split('.')[0]
            self.kwargs['extension'] = self.args[-1].split('.')[-1]
            self.args.reverse()
            self.kwargs.update({key: item for key, item in dict(zip(self.keys, self.args)).iteritems()})

        self.kwargs.update({key:item for key,item in kwargs.iteritems()})
        # check for looks folder the same as the filename.
        self.args.reverse()
        self.root = '{live}/{show}/{asset_type}/{asset_name}'.format(**self.kwargs)
        self.update_shotgun_data(**self.kwargs)
        #print self.kwargs

    def update_args(self,**kwargs):
        self.kwargs.update({key:item for key,item in kwargs.iteritems()})

    def build_params(self, action_type, extension):
        return self.registry[action_type][extension]

    def exclude(self, *args):
        self.exclude_list += args
        self.update()

    def update(self, *args):
        args = list(args)
        if not args:
            args.append(self.root)

        files = glob.glob('%s/*' % args[0])
        for file in files:
            file = file.replace('\\', '/').replace('//', '/')
            include = True
            for exclude in self.exclude_list:
                if exclude in file:
                    include = False
                    break
            if include:
                if '/_' not in file:
                    if os.path.isfile(file):

                        self.data_sets[file] = self.get_source(file)
                    else:
                        self.update(file)

    def update_shotgun_data(self, **kwargs):
        shotgun_path = '{work}/{show}/{asset_type}/COMMON/SHOTGUN/SG_{show}_{asset_type}_{asset_name}.json'.format(
            **kwargs)

        if os.path.exists(shotgun_path):
            with open(shotgun_path, 'r') as reader:
                shotgun_data = json.load(reader)
            reader.close()
            for key, item in shotgun_data.items():
                clean_key = key.replace('sg_', '')
                clean_key = clean_key.replace('_1', '')
                self.shotgun_data[clean_key] = item

    def get_source(self, filename):
        log_path = '{}.json'.format(filename)
        log_path = log_path.replace(self.kwargs['live'], self.kwargs['meta'])
        source = ''
        if os.path.exists(log_path):
            with open(log_path, 'r') as reader:
                log_data = json.load(reader)
            reader.close()
            if log_data.has_key('HEAD'):
                source = log_data['HEAD']['COMMENT']
                source = source.split('/WORK/')[-1]

        if source not in self.sources.keys():
            self.sources[source] = []
        self.sources[source].append(filename)

        base = filename.split('.')[0]
        if base not in self.data_set_groups:
            self.data_set_groups[base] = []
        self.data_set_groups[base].append(filename)
        if source not in self.data_set_groups[base]:
            self.data_set_groups[base].append(source)
        return source

    def json_print(self, **kwargs):
        print json.dumps(kwargs, sort_keys=True, indent=True)

def generateNamespace(file_name):
    if '__' in file_name:
        return file_name.split('__', 1)[-1].split('.')[0]

    name_space = file_name.split('/')[-1].split('.')[0]
    ns = name_space.split('_')
    if len(ns) > 6:
        name_space = '_'.join(ns[5:])
    return name_space

def getPreffered(args, **kwargs):
    checkBuild= False
    if 'build' in kwargs:
        checkBuild = True
        kwargs.pop('build')
    for key, items in kwargs.iteritems():
        for f in items:
            if '_CAMERA.abc' in f:
                return f, '.abc'

            if checkBuild and '/BUILD/' in ','.join(items):
                if '/BUILD/' in f and '.ma' in f:
                    return f,'.ma'
                else:
                   continue
            else:
                for a in args:
                    if f.endswith(a) and not '/BUILD/' in f:
                        return f,a
    return None, None

def referData(*args, **kwargs):
    exclude_list = kwargs.get('exclude_list', [])
    import maya.cmds as cmds
    if not 'file_path' in kwargs:
        kwargs['file_path'] = cmds.file(q=True, sn=True)
    meme = Data(file_path=kwargs['file_path'])
    meme.exclude(*exclude_list)
    loadedData = []
    for k, i, in meme.data_set_groups.iteritems():
        item = {k: i}
        if 'build' in kwargs:
            item['build'] = True

        file_name, ext = getPreffered(args, **item)
        if not file_name:
            continue
        if ':' not in file_name:
            file_name = 'W:/%s'%file_name
        if ext:
            maya_kwargs = meme.registry['refer'][ext]
            if (ext == '.ma' and '/BUILD/' in file_name) or '_SETDRESS.ma' in file_name:
                maya_kwargs = meme.registry['load'][ext]
            if 'build' not in kwargs or '_CAMERA' in file_name or 'CROWD' in file_name:
                maya_kwargs['namespace'] = generateNamespace(file_name)
            if 'CROWD' in file_name:
                if ext != '.abc':
                    continue
                cmds.createNode('gpuCache',n=maya_kwargs['namespace'])
                cmds.setAttr('%s.cacheFileName'%(maya_kwargs['namespace']),file_name,type='string')
                print '>>>>>',file_name
                loadedData.append(file_name)
                continue
            if file_name not in loadedData:
                cmds.file(file_name, **maya_kwargs)
                print '>>>>>', file_name
                loadedData.append(file_name)
                #print file_name,item
    shot_assets = '%s/SHOTASSETS/'%os.path.dirname(os.path.dirname('W:%s'%cmds.file(q=True, sn=True).split('/WORK')[-1]))
    print "shot_assets", shot_assets
    if os.path.exists(shot_assets):
        for sa in os.listdir(shot_assets):
            if '_Geo_Grp_GPU.ma' in sa:
                cmds.file('%s/%s'%(shot_assets,sa),r=True,ns = sa.split('_Geo_Grp_GPU')[0],type='mayaAscii')
    return loadedData


def animationPlayblast(*args,**kwargs):
    args = list(args) + ['.ma', '.mb', '.abc']
    kwargs['exclude_list']=['/SUBMISSION', '/CWD', 'FX_', '/SDRS', 'FXC_']
    kwargs['build']=True
    return referData(*args, **kwargs)

def animation(*args,**kwargs):
    args = list(args) + ['.ma', '.mb', '.abc']
    kwargs['exclude_list']=['/SUBMISSION', '/CWD', 'FX_', '/SDRS']
    return referData(*args, **kwargs)

def lighting(*args):
    args = list(args) + ['.abc', '.mb', '.ma']
    referData(*args)

def effects(*args):
    args = list(args) + ['.ma', '.mb', '.abc']
    referData(*args)

def crowdPlayblast(*args,**kwargs):
    args = list(args) + ['.ma', '.mb', '.abc']
    kwargs['exclude_list']=['/SUBMISSION', '/CWD', 'FX_', '/SDRS', '/GUIDE/', '/GUD']
    kwargs['build']=True
    return referData(*args, **kwargs)

if __name__ == "__main__":
    animationPlayblast(file_path='W:/F18/EP2007/SH0880/ANIMATION/ANM_F18_EP2007_SH0880.ma')
    pass
