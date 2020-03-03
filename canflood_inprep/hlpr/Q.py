'''
Created on Feb. 25, 2020

@author: cefect

helper functions w/ Qgis api
'''

#==============================================================================
# imports------------
#==============================================================================
#python
import os, configparser, logging, inspect, copy, datetime, re
import pandas as pd
import numpy as np
#qgis
from qgis.core import *
    
from qgis.analysis import QgsNativeAlgorithms
from PyQt5.QtCore import QVariant, QMetaType 

"""throws depceciationWarning"""
import processing  

mod_logger = logging.getLogger('Q') #creates a child logger of the root

#==============================================================================
# customs
#==============================================================================
if __name__ =="__main__": 
    from hlpr.exceptions import Error
else:
    from hlpr.exceptions import QError as Error
    

from hlpr.basic import *


#==============================================================================
# globals
#==============================================================================
fieldn_max_d = {'SpatiaLite':50, 'ESRI Shapefile':10}

npc_pytype_d = {'?':bool,
                'b':int,
                'd':float,
                'e':float,
                'f':float,
                'q':int,
                'h':int,
                'l':int,
                'i':int,
                'g':float,
                'U':str,
                'B':int,
                'L':int,
                'Q':int,
                'H':int,
                'I':int, 
                'O':str, #this is the catchall 'object'
                }

type_qvar_py_d = {10:str, 2:int, 135:float, 6:float, 4:int, 1:bool, 16:datetime.datetime, 12:str} #QVariant.types to pythonic types

#==============================================================================
# classes -------------
#==============================================================================

class Qcoms(object): #baseclass for working w/ pyqgis outside the native console
    
    crs_id = 4326
    crs = QgsCoordinateReferenceSystem(crs_id)
    driverName = 'SpatiaLite' #default data creation driver type
    

    out_dName = driverName #default output driver/file type
    SpatiaLite_pars = dict() #dictionary of spatialite pars

    algo_init = False #flag indicating whether the algos have been initialized
    
    out_dir = None
    overwrite=True
    
    qap = None
    
    def __init__(self,
                 logger, tag='test', feedback=None,
                 out_dir=None,
                 ):
        

        logger.info('simple wrapper inits')
        
        #setup output directory
        if out_dir is None: out_dir = os.getcwd()
        
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
            self.logger.info('created requested output directory: \n    %s'%out_dir)
        self.out_dir =out_dir
        
        #=======================================================================
        # attach inputs
        #=======================================================================
            
        if feedback is None: feedback = QgsProcessingFeedback()


        self.logger = logger.getChild('Qsimp')
        self.tag = tag
        self.feedback = feedback

        self.logger.info('Qcoms.__init__ finished w/ out_dir: \n    %s'%self.out_dir)
        
        return
    
    #==========================================================================
    # standalone methods-----------
    #==========================================================================
        
    def ini_standalone(self, ):
        #=======================================================================
        # setup qgis
        #=======================================================================
        self.qap = self.init_qgis()
        self.qproj = QgsProject.instance()
        


        self.algo_init = self.init_algos()
        
        
        self.set_vdrivers()
        
        self.mstore = QgsMapLayerStore() #build a new map store
        
        
        
        if not self.proj_checks():
            raise Error('failed checks')
        
        
        mod_logger.info('Qproj __INIT__ finished')
        
        
        return
    
    def init_qgis(self, #instantiate qgis
                  gui = False): 
        """
        WARNING: need to hold this app somewhere. call in the module you're working in (scripts)
        
        """
        log = self.logger.getChild('init_qgis')
        
        try:
            
            QgsApplication.setPrefixPath(r'C:/OSGeo4W64/apps/qgis', True)
            
            app = QgsApplication([], gui)
            #   Update prefix path
            #app.setPrefixPath(r"C:\OSGeo4W64\apps\qgis", True)
            app.initQgis()
            #logging.debug(QgsApplication.showSettings())
            log.info(' QgsApplication.initQgis. version: %s, release: %s'%
                        (Qgis.QGIS_VERSION, Qgis.QGIS_RELEASE_NAME))
            return app
        
        except:
            raise Error('QGIS failed to initiate')
        
    def init_algos(self): #initiilize processing and add providers
        """
        crashing without raising an Exception
        """
    
    
        log = self.logger.getChild('init_algos')
        
        if not isinstance(self.qap, QgsApplication):
            raise Error('qgis has not been properly initlized yet')
        
        from processing.core.Processing import Processing
    
        Processing.initialize() #crashing without raising an Exception
    
        QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
        
        log.info('processing initilzied')
        
        self.feedback = QgsProcessingFeedback()

        return True

    def set_vdrivers(self):
        
        #build vector drivers list by extension
        """couldnt find a good built-in to link extensions with drivers"""
        vlay_drivers = {'SpatiaLite':'sqlite', 'OGR':'shp'}
        
        
        #vlay_drivers = {'sqlite':'SpatiaLite', 'shp':'OGR','csv':'delimitedtext'}
        
        for ext in QgsVectorFileWriter.supportedFormatExtensions():
            dname = QgsVectorFileWriter.driverForExtension(ext)
            
            if not dname in vlay_drivers.keys():
            
                vlay_drivers[dname] = ext
            
        #add in missing/duplicated
        for vdriver in QgsVectorFileWriter.ogrDriverList():
            if not vdriver.driverName in vlay_drivers.keys():
                vlay_drivers[vdriver.driverName] ='?'
                
        self.vlay_drivers = vlay_drivers
        
        self.logger.debug('built driver:extensions dict: \n    %s'%vlay_drivers)
        
        return
        
    def set_crs(self, #load, build, and set the project crs
                authid =  None):
        
        #=======================================================================
        # setup and defaults
        #=======================================================================
        log = self.logger.getChild('set_crs')
        
        if authid is None: 
            authid = self.crs_id
        
        if not isinstance(authid, int):
            raise IOError('expected integer for crs')
        
        #=======================================================================
        # build it
        #=======================================================================
        self.crs = QgsCoordinateReferenceSystem(authid)
        
        if not self.crs.isValid():
            raise IOError('CRS built from %i is invalid'%authid)
        
        #=======================================================================
        # attach to project
        #=======================================================================
        self.qproj.setCrs(self.crs)
        
        if not self.qproj.crs().description() == self.crs.description():
            raise Error('qproj crs does not match sessions')
        
        log.info('Session crs set to EPSG: %i, \'%s\''%(authid, self.crs.description()))
           
    def proj_checks(self):
        log = self.logger.getChild('proj_checks')
        
        if not self.driverName in self.vlay_drivers:
            raise Error('unrecognized driver name')
        
        if not self.out_dName in self.vlay_drivers:
            raise Error('unrecognized driver name')
        
        log.info('project passed all checks')
        
        return True
    
    def load_vlay(self, fp, logger=None, providerLib='ogr'):
        
        assert os.path.exists(fp), 'requested file does not exist: %s'%fp
        
        if logger is None: logger = self.logger
        log = logger.getChild('load_vlay')
        
        basefn = os.path.splitext(os.path.split(fp)[1])[0]
        vlay_raw = QgsVectorLayer(fp,basefn,providerLib)
        
        
        

        # checks
        if not isinstance(vlay_raw, QgsVectorLayer): 
            raise IOError
        
        #check if this is valid
        if not vlay_raw.isValid():
            raise Error('loaded vlay \'%s\' is not valid. \n \n did you initilize?'%vlay_raw.name())
        
        #check if it has geometry
        if vlay_raw.wkbType() == 100:
            raise Error('loaded vlay has NoGeometry')
        
        
        self.mstore.addMapLayer(vlay_raw)
        
        
        vlay = vlay_raw
        dp = vlay.dataProvider()

        log.info('loaded vlay \'%s\' as \'%s\' %s geo  with %i feats from file: \n     %s'
                    %(vlay.name(), dp.storageType(), QgsWkbTypes().displayString(vlay.wkbType()), dp.featureCount(), fp))
        
        return vlay
    
    #==========================================================================
    # helper methods-----------------
    #==========================================================================
    
    def update_cf(self, #update one parameter  control file 
                  new_pars_d, #new paraemeters {section : {valnm : value }}
                  cf_fp = None):
        
        log = self.logger.getChild('update_cf')
        
        #get defaults
        if cf_fp is None: cf_fp = self.cf_fp
        
        assert os.path.exists(cf_fp), 'bad cf_fp: %s'%cf_fp
        
        #initiliae the parser
        pars = configparser.ConfigParser(allow_no_value=True)
        _ = pars.read(cf_fp) #read it from the new location
        
        #loop and make updates
        for section, val_t in new_pars_d.items():
            assert isinstance(val_t, tuple), '\"%s\' has bad subtype: %s'%(section, type(val_t))
            assert section in pars, 'requested section \'%s\' not in the pars!'%section
            
            for subval in val_t:
                #value key pairs
                if isinstance(subval, dict):
                    for valnm, value in subval.items():
                        pars.set(section, valnm, value)
                        
                #single values    
                elif isinstance(subval, str):
                    pars.set(section, subval)
                    
                else:
                    raise Error('unrecognized value type: %s'%type(subval))
                
        
        #write the config file 
        with open(cf_fp, 'w') as configfile:
            pars.write(configfile)
            
        log.info('updated contyrol file w/ %i pars at :\n    %s'%(
            len(new_pars_d), cf_fp))
        
        return
    
    def output_df(self, #dump some outputs
                      df, 
                      out_fn,
                      out_dir = None,
                      overwrite=None,
                      write_index=False,
            ):
        #======================================================================
        # defaults
        #======================================================================
        if out_dir is None: out_dir = self.out_dir
        if overwrite is None: overwrite = self.overwrite
        log = self.logger.getChild('output')
        
        #======================================================================
        # prechecks
        #======================================================================
        assert isinstance(out_dir, str), 'unexpected type on out_dir: %s'%type(out_dir)
        assert os.path.exists(out_dir), 'requested output directory doesnot exist: \n    %s'%out_dir
        assert isinstance(df, pd.DataFrame)
        assert len(df) >0, 'no data'
        
        
        #extension check
        if not out_fn.endswith('.csv'):
            out_fn = out_fn+'.csv'
        
        #output file path
        out_fp = os.path.join(out_dir, out_fn)
        
        #======================================================================
        # checeks
        #======================================================================
        if os.path.exists(out_fp):
            log.warning('file exists \n    %s'%out_fp)
            if not overwrite:
                raise Error('file already exists')
            

        #======================================================================
        # writ eit
        #======================================================================
        df.to_csv(out_fp, index=write_index)
        
        log.info('wrote to %s to file: \n    %s'%(str(df.shape), out_fp))
        
        self.out_fp = out_fp #set for other methods
        
        return out_fp
    
    #==========================================================================
    # algos--------------
    #==========================================================================
    def deletecolumn(self,
                     in_vlay,
                     fieldn_l, #list of field names
                     invert=False, #whether to invert selected field names
                     layname = None,


                     ):

        #=======================================================================
        # presets
        #=======================================================================
        algo_nm = 'qgis:deletecolumn'
        log = self.logger.getChild('deletecolumn')
        self.vlay = in_vlay

        #=======================================================================
        # field manipulations
        #=======================================================================
        fieldn_l = self._field_handlr(in_vlay, fieldn_l,  invert=invert)
        
            

        if len(fieldn_l) == 0:
            log.debug('no fields requsted to drop... skipping')
            return self.vlay

        #=======================================================================
        # assemble pars
        #=======================================================================
        #assemble pars
        ins_d = { 'COLUMN' : fieldn_l, 
                 'INPUT' : in_vlay, 
                 'OUTPUT' : 'TEMPORARY_OUTPUT'}
        
        log.debug('executing \'%s\' with ins_d: \n    %s'%(algo_nm, ins_d))
        
        res_d = processing.run(algo_nm, ins_d, feedback=self.feedback)
        
        res_vlay = res_d['OUTPUT']

        
        #===========================================================================
        # post formatting
        #===========================================================================
        if layname is None: 
            layname = '%s_delf'%self.vlay.name()
            
        res_vlay.setName(layname) #reset the name

        
        return res_vlay 

    def joinattributesbylocation(self,
                                 #data definitions
                                 vlay,
                                 join_vlay, #layer from which to extract attribue values onto th ebottom vlay
                                 jlay_fieldn_l, #list of field names to extract from the join_vlay
                                 selected_only = False,
                                 jvlay_selected_only = False, #only consider selected features on the join layer
                                 
                                 #algo controls
                                 prefix = '',
                                 method=0, #one-to-many
                                 predicate_l = ['intersects'],#list of geometric serach predicates
                                 discard_nomatch = False, #Discard records which could not be joined
                                 
                                 #data expectations
                                 join_nullvs = True, #allow null values on  jlay_fieldn_l on join_vlay
                                 join_df = None, #if join_nullvs=FALSE, data to check for nulls (skips making a vlay_get_fdf)
                                 allow_field_rename = False, #allow joiner fields to be renamed when mapped onto the main
                                 allow_none = False,

                                 #geometry expectations
                                 expect_all_hits = False, #wheter every main feature intersects a join feature
                                 expect_j_overlap = False, #wheter to expect the join_vlay to beoverlapping
                                 expect_m_overlap = False, #wheter to expect the mainvlay to have overlaps
                     ):
        """        
        discard_nomatch: 
            TRUE: two resulting layers have no features in common
            FALSE: in layer retains all non matchers, out layer only has the non-matchers?
        
        METHOD: Join type

        - 0: Create separate feature for each located feature (one-to-many)
        - 1: Take attributes of the first located feature only (one-to-one)
        
        """
        #=======================================================================
        # presets
        #=======================================================================
        self.vlay = vlay
        algo_nm = 'qgis:joinattributesbylocation'
        
        predicate_d = {'intersects':0,'contains':1,'equals':2,'touches':3,'overlaps':4,'within':5, 'crosses':6}
        

        log = self.logger.getChild('joinattributesbylocation')

        jlay_fieldn_l = self._field_handlr(join_vlay, 
                                           jlay_fieldn_l, 
                                           invert=False)
        
        jgeot = vlay_get_bgeo_type(join_vlay)
        mgeot = vlay_get_bgeo_type(self.vlay)
        
        mfcnt = self.vlay.dataProvider().featureCount()
        #jfcnt = join_vlay.dataProvider().featureCount()
        
        mfnl = vlay_fieldnl(self.vlay)
        
        expect_overlaps = expect_j_overlap or expect_m_overlap
        #=======================================================================
        # geometry expectation prechecks
        #=======================================================================
        if not (jgeot == 'polygon' or mgeot == 'polygon'):
            raise Error('one of the layres has to be a polygon')
        
        if not jgeot=='polygon':
            if expect_j_overlap:
                raise Error('join vlay is not a polygon, expect_j_overlap should =False')
            
        if not mgeot=='polygon':
            if expect_m_overlap:
                raise Error('main vlay is not a polygon, expect_m_overlap should =False')
        
        if expect_all_hits:
            if discard_nomatch:
                raise Error('discard_nomatch should =FALSE if  you expect all hits')
            
            if allow_none:
                raise Error('expect_all_hits=TRUE and allow_none=TRUE')

            
        #method checks
        if method==0:
            if not jgeot == 'polygon':
                raise Error('passed method 1:m but jgeot != polygon')
            
        if not expect_j_overlap:
            if not method==0:
                raise Error('for expect_j_overlap=False, method must = 0 (1:m) for validation')

               
        #=======================================================================
        # data expectation checks
        #=======================================================================
        #make sure none of the joiner fields are already on the layer
        if len(mfnl)>0: #see if there are any fields on the main
            l = linr(jlay_fieldn_l, mfnl, result_type='matching')
            
            if len(l) > 0:
                #w/a prefix
                if not prefix=='':
                    log.debug('%i fields on the joiner \'%s\' are already on \'%s\'... prefixing w/ \'%s\': \n    %s'%(
                        len(l), join_vlay.name(), self.vlay.name(), prefix, l))
                else:
                    log.debug('%i fields on the joiner \'%s\' are already on \'%s\'...renameing w/ auto-sufix: \n    %s'%(
                        len(l), join_vlay.name(), self.vlay.name(), l))
                    
                    if not allow_field_rename:
                        raise Error('%i field names overlap: %s'%(len(l), l))
                
                
        #make sure that the joiner attributes are not null
        if not join_nullvs:
            if jvlay_selected_only:
                raise Error('not implmeneted')
            
            #pull thedata
            if join_df is None:
                join_df = vlay_get_fdf(join_vlay, fieldn_l=jlay_fieldn_l, db_f=self.db_f, logger=log)
                
            #slice to the columns of interest
            join_df = join_df.loc[:, jlay_fieldn_l]
                
            #check for nulls
            booldf = join_df.isna()
            
            if np.any(booldf):
                raise Error('got %i nulls on \'%s\' field %s data'%(
                    booldf.sum().sum(), join_vlay.name(), jlay_fieldn_l))
            

        #=======================================================================
        # assemble pars
        #=======================================================================
        #convert predicate to code
        pred_code_l = [predicate_d[name] for name in predicate_l]

            
        #selection flags
        if selected_only:
            """WARNING! This will limit the output to only these features
            (despite the DISCARD_NONMATCHING flag)"""
            
            main_input = self._get_sel_obj(self.vlay)
        else:
            main_input = self.vlay
        
        if jvlay_selected_only:
            join_input = self._get_sel_obj(join_vlay)
        else:
            join_input = join_vlay

        #assemble pars
        ins_d = { 'DISCARD_NONMATCHING' : discard_nomatch, 
                 'INPUT' : main_input, 
                 'JOIN' : join_input, 
                 'JOIN_FIELDS' : jlay_fieldn_l,
                 'METHOD' : method, 
                 'OUTPUT' : 'TEMPORARY_OUTPUT', 
                 #'NON_MATCHING' : 'TEMPORARY_OUTPUT', #not working as expected. see get_misses
                 'PREDICATE' : pred_code_l, 
                 'PREFIX' : prefix}
        
        
        
        log.info('extracting %i fields from %i feats from \'%s\' to \'%s\' join fields: %s'%
                  (len(jlay_fieldn_l), join_vlay.dataProvider().featureCount(), 
                   join_vlay.name(), self.vlay.name(), jlay_fieldn_l))
        
        log.debug('executing \'%s\' with ins_d: \n    %s'%(algo_nm, ins_d))
        
        res_d = processing.run(algo_nm, ins_d, feedback=self.feedback)
        
        res_vlay, join_cnt = res_d['OUTPUT'], res_d['JOINED_COUNT']
        
        """
        res_d['OUTPUT'].dataProvider().featureCount()
        """
        
        log.debug('got results: \n    %s'%res_d)
        

        #===========================================================================
        # post formatting
        #===========================================================================
        #======================================================================
        # if self.layname is None: 
        #     self.layname = '%s_fjoin'%self.vlay.name()
        #     
        # res_vlay.setName(self.layname) #reset the name
        #======================================================================
        

        #===========================================================================
        # post checks
        #===========================================================================
        
        hit_fcnt = res_vlay.dataProvider().featureCount()
        
        
        if not expect_overlaps:
            if not discard_nomatch:
                if not hit_fcnt == mfcnt:
                    raise Error('in and out fcnts dont match')

        else:
            log.debug('expect_overlaps=False, unable to check fcnts')



        #all misses
        if join_cnt == 0:
            log.warning('got no joins from \'%s\' to \'%s\''%(
                self.vlay.name(), join_vlay.name()))
            
            if not allow_none:
                raise Error('got no joins!')
            
            if discard_nomatch:
                if not hit_fcnt == 0:
                    raise Error('no joins but got some hits')
           
        #some hits 
        else:
            #check there are no nulls
            if discard_nomatch and not join_nullvs:
                #get data on first joiner
                fid_val_ser = vlay_get_fdata(res_vlay, jlay_fieldn_l[0], logger=log, fmt='ser')
                
                if np.any(fid_val_ser.isna()):                  
                    raise Error('discard=True and join null=FALSe but got %i (of %i) null \'%s\' values in the reuslt'%(
                        fid_val_ser.isna().sum(), len(fid_val_ser), fid_val_ser.name
                        ))
                
        #=======================================================================
        # miss retrival
        #=======================================================================
        """removed"""
        #=======================================================================
        # get the new field names
        #=======================================================================
        new_fn_l = set(vlay_fieldnl(res_vlay)).difference(vlay_fieldnl(self.vlay))
                    
        #=======================================================================
        # wrap
        #=======================================================================
        log.debug('finished joining %i fields from %i (of %i) feats from \'%s\' to \'%s\' join fields: %s'%
                  (len(new_fn_l), join_cnt, self.vlay.dataProvider().featureCount(),
                   join_vlay.name(), self.vlay.name(), new_fn_l))
        

        return res_vlay, new_fn_l, join_cnt
    
    #==========================================================================
    # privates----------
    #==========================================================================
    def _field_handlr(self, #common handling for fields
                      vlay, #layer to check for field presence
                      fieldn_l, #list of fields to handle
                      invert = False,
                      ):
        
        log = self.logger.getChild('_field_handlr')

        #=======================================================================
        # all flag
        #=======================================================================
        if isinstance(fieldn_l, str):
            if fieldn_l == 'all':

                fieldn_l = vlay_fieldnl(vlay)
                log.debug('user passed \'all\', retrieved %i fields: \n    %s'%(
                    len(fieldn_l), fieldn_l))
                                
                
            else:
                raise Error('unrecognized fieldn_l\'%s\''%fieldn_l)
            
        #=======================================================================
        # type setting
        #=======================================================================
        if isinstance(fieldn_l, tuple) or isinstance(fieldn_l, np.ndarray) or isinstance(fieldn_l, set):
            fieldn_l = list(fieldn_l)
            
        #=======================================================================
        # checking
        #=======================================================================
        if not isinstance(fieldn_l, list):
            raise Error('expected a list for fields, instead got \n    %s'%fieldn_l)
        
        
    
    
        vlay_check(vlay, exp_fieldns=fieldn_l)
        
        
        #=======================================================================
        # #handle inversions
        #=======================================================================
        if invert:
            big_fn_s = set(vlay_fieldnl(vlay)) #get all the fields

            #get the difference
            fieldn_l = list(big_fn_s.difference(set(fieldn_l)))
            
            self.logger.debug('inverted selection from %i to %i fields'%
                      (len(big_fn_s),  len(fieldn_l)))
            
            
        
        
        return fieldn_l
    
    def _get_sel_obj(self, vlay): #get the processing object for algos with selections
        
        log = self.logger.getChild('_get_sel_obj')
        
        if vlay.selectedFeatureCount() == 0:
            raise Error('Nothing selected. exepects some pre selection')
        
        """consider moving this elsewhere"""
        #handle project layer store
        if QgsProject.instance().mapLayer(vlay.id()) is None:
            #layer not on project yet. add it
            if QgsProject.instance().addMapLayer(vlay, False) is None:
                raise Error('failed to add map layer \'%s\''%vlay.name())

        
       
        log.debug('based on %i selected features from \'%s\': %s'
                  %(len(vlay.selectedFeatureIds()), vlay.name(), vlay.selectedFeatureIds()))
            
        return QgsProcessingFeatureSourceDefinition(vlay.id(), True)
    
    def _in_out_checking(self,res_vlay,
                         ):
        
        """placeholder"""
        #===========================================================================
        # setups and defaults
        #===========================================================================
        log = self.logger.getChild('_in_out_checking')


            
        return

#==============================================================================
# FUNCTIONS----------
#==============================================================================
def vlay_check( #helper to check various expectations on the layer
                    vlay,
                    exp_fieldns = None, #raise error if these field names are OUT
                    uexp_fieldns = None, #raise error if these field names are IN
                    real_atts = None, #list of field names to check if attribute value are all real
                    bgeot = None, #basic geo type checking
                    fcnt = None, #feature count checking. accepts INT or QgsVectorLayer
                    fkey = None, #optional secondary key to check 
                    mlay = False, #check if its a memory layer or not
                    chk_valid = False, #check layer validty
                    logger = mod_logger, 
                    db_f = False,
                    ):
    #=======================================================================
    # prechecks
    #=======================================================================
    if vlay is None:
        raise Error('got passed an empty vlay')
    
    if not isinstance(vlay, QgsVectorLayer):
        raise Error('unexpected type: %s'%type(vlay))
    
    log = logger.getChild('vlay_check')
    checks_l = []
    

    #=======================================================================
    # expected field names
    #=======================================================================
    if not is_null(exp_fieldns): #robust null checking
        skip=False
        if isinstance(exp_fieldns, str):
            if exp_fieldns=='all':
                skip=True
            
        
        
        if not skip:
            fnl = linr(exp_fieldns, vlay_fieldnl(vlay),
                                      'expected field names', vlay.name(),
                                      result_type='missing', logger=log, fancy_log=db_f)
            
            if len(fnl)>0:
                raise Error('%s missing expected fields: %s'%(
                    vlay.name(), fnl))
                
            checks_l.append('exp_fieldns=%i'%len(exp_fieldns))
        
    #=======================================================================
    # unexpected field names
    #=======================================================================
        
    if not is_null(uexp_fieldns): #robust null checking
        #fields on the layer
        if len(vlay_fieldnl(vlay))>0:
        
            fnl = linr(uexp_fieldns, vlay_fieldnl(vlay),
                                      'un expected field names', vlay.name(),
                                      result_type='matching', logger=log, fancy_log=db_f)
            
            if len(fnl)>0:
                raise Error('%s contains unexpected fields: %s'%(
                    vlay.name(), fnl))
                
        #no fields on the layer
        else:
            pass
            
        checks_l.append('uexp_fieldns=%i'%len(uexp_fieldns))
        
    
    #=======================================================================
    # null value check
    #=======================================================================
    #==========================================================================
    # if not real_atts is None:
    #     
    #     #pull this data
    #     df = vlay_get_fdf(vlay, fieldn_l = real_atts, logger=log)
    #     
    #     #check for nulls
    #     if np.any(df.isna()):
    #         raise Error('%s got %i nulls on %i expected real fields: %s'%(
    #             vlay.name(), df.isna().sum().sum(), len(real_atts), real_atts))
    #         
    #     
    #     checks_l.append('real_atts=%i'%len(real_atts))
    #==========================================================================

            
            
    #=======================================================================
    # basic geometry type
    #=======================================================================
    #==========================================================================
    # if not bgeot is None:
    #     bgeot_lay =  vlay_get_bgeo_type(vlay)
    #     
    #     if not bgeot == bgeot_lay:
    #         raise Error('basic geometry type expectation \'%s\' does not match layers \'%s\''%(
    #             bgeot, bgeot_lay))
    #         
    #     checks_l.append('bgeot=%s'%bgeot)
    #==========================================================================
            
    #=======================================================================
    # feature count
    #=======================================================================
    if not fcnt is None:
        if isinstance(fcnt, QgsVectorLayer):
            fcnt=fcnt.dataProvider().featureCount()
        
        if not fcnt == vlay.dataProvider().featureCount():
            raise Error('\'%s\'s feature count (%i) does not match %i'%(
                vlay.name(), vlay.dataProvider().featureCount(), fcnt))
            
        checks_l.append('fcnt=%i'%fcnt)
        
    #=======================================================================
    # fkey
    #=======================================================================
#==============================================================================
#     if isinstance(fkey, str):
#         fnl = vlay_fieldnl(vlay)
#         
#         if not fkey in fnl:
#             raise Error('fkey \'%s\' not in the fields'%fkey)
#         
#         fkeys_ser = vlay_get_fdata(vlay, fkey, logger=log, fmt='ser').sort_values()
#         
#         if not np.issubdtype(fkeys_ser.dtype, np.number):
#             raise Error('keys are non-numeric. type: %s'%fkeys_ser.dtype)
#         
#         if not fkeys_ser.is_unique:
#             raise Error('\'%s\' keys are not unique'%fkey)
# 
#         if not fkeys_ser.is_monotonic:
#             raise Error('fkeys are not monotonic')
#         
#         if np.any(fkeys_ser.isna()):
#             raise Error('fkeys have nulls')
#         
#         checks_l.append('fkey \'%s\'=%i'%(fkey, len(fkeys_ser)))
#==============================================================================
        
    #=======================================================================
    # storage type
    #=======================================================================
    if mlay:
        if not 'Memory' in vlay.dataProvider().storageType():
            raise Error('\"%s\' unexpected storage type: %s'%(
                vlay.name(), vlay.dataProvider().storageType()))
        
        checks_l.append('mlay')
        
    #=======================================================================
    # validty
    #=======================================================================
    #==========================================================================
    # if chk_valid:
    #     vlay_chk_validty(vlay, chk_geo=True)
    #     
    #     checks_l.append('validity')
    #==========================================================================
        
    
    #=======================================================================
    # wrap
    #=======================================================================

    log.debug('\'%s\' passed %i checks: %s'%(
        vlay.name(), len(checks_l), checks_l))
    return
    
def load_vlay( #load a layer from a file
        fp,
        providerLib='ogr',
        logger=mod_logger):
    log = logger.getChild('load_vlay') 
    
    
    assert os.path.exists(fp), 'requested file does not exist: %s'%fp

    
    basefn = os.path.splitext(os.path.split(fp)[1])[0]
    

    #Import a Raster Layer
    vlay_raw = QgsVectorLayer(fp,basefn,providerLib)
    
    #check if this is valid
    if not vlay_raw.isValid():
        log.error('loaded vlay \'%s\' is not valid. \n \n did you initilize?'%vlay_raw.name())
        raise Error('vlay loading produced an invalid layer')
    
    #check if it has geometry
    if vlay_raw.wkbType() == 100:
        log.error('loaded vlay has NoGeometry')
        raise Error('no geo')
    
    #==========================================================================
    # report
    #==========================================================================
    vlay = vlay_raw
    dp = vlay.dataProvider()

    log.info('loaded vlay \'%s\' as \'%s\' %s geo  with %i feats from file: \n     %s'
                %(vlay.name(), dp.storageType(), QgsWkbTypes().displayString(vlay.wkbType()), dp.featureCount(), fp))
    
    return vlay


def vlay_write( #write  a layer to file
        vlay, out_fp, 
        destCRS=None,
        driverName='GPKG',
        fileEncoding = "CP1250", 
        overwrite=False,
        logger=mod_logger):
    
    #==========================================================================
    # defaults
    #==========================================================================
    log = logger.getChild('vlay_write')
    
    if destCRS is None: destCRS = vlay.dataProvider().crs()
    
    
    #===========================================================================
    # checks
    #===========================================================================
    #file extension
    fhead, ext = os.path.splitext(out_fp)
    
    if not 'gpkg' in ext:
        raise Error('unexpected extension: %s'%ext)
    
    if os.path.exists(out_fp):
        msg = 'requested file path already exists!. overwrite=%s \n    %s'%(
            overwrite, out_fp)
        if overwrite:
            log.warning(msg)
        else:
            raise Error(msg)
        
    
    if vlay.dataProvider().featureCount() == 0:
        raise Error('\'%s\' has no features!'%(
            vlay.name()))
        
    if not vlay.isValid():
        Error('passed invalid layer')
        
    if not destCRS.isValid(): 
        raise Error('invalid destCrs')
        
    
    error = QgsVectorFileWriter.writeAsVectorFormat(
            vlay, out_fp, fileEncoding, destCRS,
            driverName=driverName,
            #layerOptions = layerOptions,
            #datasourceOptions = datasourceOptions,
            )
    
    
    #=======================================================================
    # wrap and check
    #=======================================================================
      
    if error[0] == QgsVectorFileWriter.NoError:
        log.info('layer \' %s \' written to: \n     %s'%(vlay.name(),out_fp))
        return 
     
    raise Error('FAILURE on writing layer \' %s \'  with code:\n    %s \n    %s'%(vlay.name(),error, out_fp))
    
    
    
    
def vlay_get_fdf( #pull all the feature data and place into a df
                    vlay,
                    fmt='df', #result fomrat key. 
                        #dict: {fid:{fieldname:value}}
                        #df: index=fids, columns=fieldnames
                    
                    #limiters
                    request = None, #request to pull data. for more customized requestes.
                    fieldn_l = None, #or field name list. for generic requests
                    
                    #modifiers
                    reindex = None, #optinal field name to reindex df by
                    
                    #expectations
                    expect_all_real = False, #whether to expect all real results
                    allow_none = False,
                    
                    db_f = False,logger=mod_logger):
    """
    performance improvement
    
    Warning: requests with getFeatures arent working as expected for memory layers
    
    this could be combined with vlay_get_feats()
    also see vlay_get_fdata() (for a single column)
    
    
    RETURNS
    a dictionary in the Qgis attribute dictionary format:
        key: generally feat.id()
        value: a dictionary of {field name: attribute value}

    """
    #===========================================================================
    # setups and defaults
    #===========================================================================
    
    log = logger.getChild('vlay_get_fdf')
    
    all_fnl = [fieldn.name() for fieldn in vlay.fields().toList()]
    
    if fieldn_l is None: #use all the fields
        fieldn_l = all_fnl
        
    else:
        vlay_check(vlay, fieldn_l, logger=logger, db_f=db_f)
        

    
    if allow_none:
        if expect_all_real:
            raise Error('cant allow none and expect all reals')
        
    
    #===========================================================================
    # prechecks
    #===========================================================================
    if not reindex is None:
        if not reindex in fieldn_l:
            raise Error('requested reindexer \'%s\' is not a field name'%reindex)
    
    if not vlay.dataProvider().featureCount()>0:
        raise Error('no features!')

    if len(fieldn_l) == 0:
        raise Error('no fields!')
    
    if fmt=='dict' and not (len(fieldn_l)==len(all_fnl)):
        raise Error('dict results dont respect field slicing')
    
    #===========================================================================
    # build the request
    #===========================================================================
    if request is None:
        """WARNING: this doesnt seem to be slicing the fields.
        see Alg().deletecolumns()
            but this will re-key things
        
        request = QgsFeatureRequest().setSubsetOfAttributes(fieldn_l,vlay.fields())"""
        request = QgsFeatureRequest()
        
    #never want geometry   
    request = request.setFlags(QgsFeatureRequest.NoGeometry) 
               

    log.debug('extracting data from \'%s\' on fields: %s'%(vlay.name(), fieldn_l))
    #===========================================================================
    # loop through each feature and extract the data
    #===========================================================================
    
    fid_attvs = dict() #{fid : {fieldn:value}}

    for feat in vlay.getFeatures(request):
        
        #zip values
        fid_attvs[feat.id()] = feat.attributes()


    #===========================================================================
    # post checks
    #===========================================================================
    if not len(fid_attvs) == vlay.dataProvider().featureCount():
        log.debug('data result length does not match feature count')

        if not request.filterType()==3: #check if a filter fids was passed
            """todo: add check to see if the fiter request length matches tresult"""
            raise Error('no filter and data length mismatch')
        
    #check the field lengthes
    if not len(all_fnl) == len(feat.attributes()):
        raise Error('field length mismatch')

    #empty check 1
    if len(fid_attvs) == 0:
        log.warning('failed to get any data on layer \'%s\' with request'%vlay.name())
        if not allow_none:
            raise Error('no data found!')
        else:
            if fmt == 'dict': 
                return dict()
            elif  fmt == 'df':
                return pd.DataFrame()
            else:
                raise Error('unexpected fmt type')
            
    
    #===========================================================================
    # result formatting
    #===========================================================================
    log.debug('got %i data elements for \'%s\''%(
        len(fid_attvs), vlay.name()))
    
    if fmt == 'dict':
        
        return fid_attvs
    elif fmt=='df':
        
        #build the dict
        
        df_raw = pd.DataFrame.from_dict(fid_attvs, orient='index', columns=all_fnl)
        
        
        #handle column slicing and Qnulls
        """if the requester worked... we probably  wouldnt have to do this"""
        df = df_raw.loc[:, tuple(fieldn_l)].replace(NULL, np.nan)
        

        
        if isinstance(reindex, str):
            """
            reindex='zid'
            view(df)
            """
            #try and add the index (fids) as a data column
            try:
                df = df.join(pd.Series(df.index,index=df.index, name='fid'))
            except:
                log.debug('failed to preserve the fids.. column already there?')
            
            #re-index by the passed key... should copy the fids over to 'index
            df = df.set_index(reindex, drop=True)
            
            log.debug('reindexed data by \'%s\''%reindex)
            
        return df
            



        
    #===========================================================================
    # wrap and reuslt
    #===========================================================================
    
    return df
    
    
def vlay_get_fdata( #get data for a single field from all the features
            vlay,
            fieldn = None, #get a field name. 'None' returns a dictionary of np.nan
            geopropn = None, #get a geometry property
            geo_obj = False, #whether to just get the geometry object
            request = None, #additional requester (limiting fids). fieldn still required. additional flags added
            selected= False, #whether to limit data to just those selected features
            fmt = 'dict', #format to return results in
                #'singleton' expect and aprovide a unitary value
                
            expect_all_real = False, #whether to expect all real results
            dropna = False, #whether to drop nulls from the results
            allow_none = False,
            
            logger = mod_logger, db_f=False):
    
    """
    TODO: combine this with vlay_get_fdatas
    consider combining with vlay_get_feats
    
    I'm not sure how this will handle requests w/ expressions
    """
    
    log = logger.getChild('vlay_get_fdata')
    
    if request is None:
        request = QgsFeatureRequest()
    
    #===========================================================================
    # prechecks
    #===========================================================================
    if geo_obj:
        if fmt == 'df': raise IOError
        if not geopropn is None: raise IOError
        
    if dropna:
        if expect_all_real:
            raise Error('cant expect_all_reals AND dropna')
    
    if allow_none:
        if expect_all_real:
            raise Error('cant allow none and expect all reals')
        
    vlay_check(vlay, exp_fieldns=[fieldn], logger=log, db_f=db_f)
    
    #===========================================================================
    # build the request
    #===========================================================================
    #no geometry
    if (geopropn is None) and (not geo_obj): 
        
        if fieldn is None: 
            raise Error('no field name provided')
        

        request = request.setFlags(QgsFeatureRequest.NoGeometry)
        request = request.setSubsetOfAttributes([fieldn],vlay.fields())
        
    else:
        
        request = request.setNoAttributes() #dont get any attributes
        
    #===========================================================================
    # selection limited
    #===========================================================================
    if selected:
        """
        todo: check if there is already a fid filter placed on the reuqester
        """
        log.debug('limiting data pull to %i selected features on \'%s\''%(
            vlay.selectedFeatureCount(), vlay.name()))
        
        sfids = vlay.selectedFeatureIds()
        
        request = request.setFilterFids(sfids)
        
    #===========================================================================
    # loop through and collect hte data
    #===========================================================================

    d = dict() #empty container for results
    for feat in vlay.getFeatures(request):
        
        #=======================================================================
        # get geometry
        #=======================================================================
        if geo_obj:
            d[feat.id()] = feat.geometry()
            
        #=======================================================================
        # get a geometry property
        #=======================================================================
        elif not geopropn is None:
            geo = feat.geometry()
            
            func = getattr(geo, geopropn) #get the method
            
            d[feat.id()] = func() #call the method and store

            
        #=======================================================================
        # field request
        #=======================================================================
        else:
            #empty shortcut
            if qisnull(feat.attribute(fieldn)): 
                d[feat.id()] = np.nan
            else: #pull real data
                d[feat.id()] = feat.attribute(fieldn)
        

    log.debug('retrieved %i attributes from features on \'%s\''%(
        len(d), vlay.name()))
              
    #===========================================================================
    # null handling
    #===========================================================================
    if selected:
        if not len(d) == vlay.selectedFeatureCount():
            raise Error('failed to get data matching %i selected features'%(
                vlay.selectedFeatureCount()))
    
    if expect_all_real:
        boolar = np.isnan(np.array(list(d.values()))) 
        if np.any(boolar):
            raise Error('got %i nulls'%boolar.sum())
        
    if dropna:
        """faster to use dfs?"""
        log.debug('dropping nulls from %i'%len(d))
        
        d2 = dict()
        
        for k, v in d.items():
            if np.isnan(v):
                continue
            d2[k] = v
            
        d = d2 #reset
        
    #===========================================================================
    # post checks
    #===========================================================================
    if len(d) == 0:
        log.warning('got no results! from \'%s\''%(
            vlay.name()))
        if not allow_none:
            raise Error('allow_none=FALSE and no results')
        
        """
        view(vlay)
        """
        
    
    #===========================================================================
    # results
    #===========================================================================

  
    
    if fmt == 'dict': 
        return d
    elif fmt == 'df': 
        return pd.DataFrame(pd.Series(d, name=fieldn))
    elif fmt == 'singleton':
        if not len(d)==1:
            raise Error('expected singleton')
        return next(iter(d.values()))
    
    elif fmt == 'ser': 
        return pd.Series(d, name=fieldn)
    else: 
        raise IOError

def vlay_new_mlay(#create a new mlay
                      gtype, #"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", or "MultiPolygon".
                      crs,
                      layname,
                      qfields,
                      feats_l,
                      mstore = True, #whether to add the layer to the store
                      

                      
                      logger=mod_logger, db_f = False,
                      chk_geo = False, #if db_f=True, whether to check the loaded geometry(slow)
                      ):
        #=======================================================================
        # defaults
        #=======================================================================
        log = logger.getChild('vlay_new_mlay')

        #=======================================================================
        # prechecks
        #=======================================================================
        if not isinstance(layname, str):
            raise Error('expected a string for layname, isntead got %s'%type(layname))
        
        if gtype=='None':
            log.warning('constructing mlay w/ \'None\' type')
        #=======================================================================
        # assemble into new layer
        #=======================================================================
        #initilzie the layer
        EPSG_code=int(crs.authid().split(":")[1]) #get teh coordinate reference system of input_layer
        uri = gtype+'?crs=epsg:'+str(EPSG_code)+'&index=yes'
        
        vlaym = QgsVectorLayer(uri, layname, "memory")
        
        # add fields
        if not vlaym.dataProvider().addAttributes(qfields):
            raise Error('failed to add fields')
        
        vlaym.updateFields()
        
        #add feats
        if not vlaym.dataProvider().addFeatures(feats_l):
            raise Error('failed to addFeatures')
        
        vlaym.updateExtents()
        

        
        #=======================================================================
        # checks
        #=======================================================================
        if vlaym.wkbType() == 100:
            msg = 'constructed layer \'%s\' has NoGeometry'%vlaym.name()
            if gtype == 'None':
                log.debug(msg)
            else:
                raise Error(msg)

        
        log.debug('constructed \'%s\''%vlaym.name())
        return vlaym
    
    
def vlay_new_df(#build a vlay from a df
            df_raw,
            crs,
            
            geo_d = None, #container of geometry objects {fid: QgsGeometry}
            geo_fn_tup = None, #if geo_d=None, tuple of field names to search for coordinate data
            
            layname='df',

            allow_fid_mismatch = False,
            
            infer_dtypes = True, #whether to referesh the dtyping in the df
            
            driverName = 'GPKG',
            
            #expectations
            expect_unique_colns = True,

            logger=mod_logger, db_f = False,
            ):
        #=======================================================================
        # setup
        #=======================================================================
        log = logger.getChild('vlay_new_df')    

            
            
        #=======================================================================
        # precheck
        #=======================================================================
        df = df_raw.copy()
        
        #======================================================================
        # #make sure none of hte field names execeed the driver limitations
        # max_len = self.fieldn_max_d[self.driverName]
        #======================================================================
        max_len = 30
        
        
        #check lengths
        boolcol = df_raw.columns.str.len() >= max_len
        
        if np.any(boolcol):
            log.warning('passed %i columns which exeed the max length %i for driver \'%s\'.. truncating: \n    %s'%(
                boolcol.sum(), max_len, driverName, df_raw.columns.values[boolcol]))
            
            
            df.columns = df.columns.str.slice(start=0, stop=max_len-1)

        
        #make sure the columns are unique
        if not df.columns.is_unique:
            """
            this can happen especially when some field names are super long and have their unique parts truncated
            """
            boolcol = df.columns.duplicated(keep='first')
            
            log.warning('got %i duplicated columns: \n    %s'%(
                boolcol.sum(), df.columns[boolcol].values))
            
            if expect_unique_colns:
                raise Error('got non unique columns')
            
            #drop the duplicates
            log.warning('dropping second duplicate column')
            df = df.loc[:, ~boolcol]
        
            
        #===========================================================================
        # assemble the features
        #===========================================================================
        """this does its own index check"""
        
        feats_d = feats_build(df, logger=log, geo_d = geo_d,infer_dtypes=infer_dtypes,
                                        geo_fn_tup = geo_fn_tup, 
                                        allow_fid_mismatch=allow_fid_mismatch, db_f=db_f)
        
        
        #=======================================================================
        # get the geo type
        #=======================================================================
        if not geo_d is None:
            #pull geometry type from first feature
            gtype = QgsWkbTypes().displayString(next(iter(geo_d.values())).wkbType())
        elif not geo_fn_tup is None:
            gtype = 'Point'
        else:
            gtype = 'None'
            
            
        #===========================================================================
        # buidl the new layer
        #===========================================================================
        vlay = vlay_new_mlay(gtype, #no geo
                             crs, 
                             layname,
                             list(feats_d.values())[0].fields(),
                             list(feats_d.values()),
                             logger=log,
                             )
        
        #=======================================================================
        # post check
        #=======================================================================
        if db_f:
            if vlay.wkbType() == 100:
                raise Error('constructed layer has NoGeometry')
            #vlay_chk_validty(vlay, chk_geo=True, logger=log)


        
        return vlay
    

            
def vlay_fieldnl(vlay):
    return [field.name() for field in vlay.fields()]


def feats_build( #build a set of features from teh passed data
                 data, #data from which to build features from (either df or qvlayd)
                 
                 geo_d = None, #container of geometry objects {fid: QgsGeometry}
                 geo_fn_tup = None, #if geo_d=None, tuple of field names to search for coordinate data
                 
                 allow_fid_mismatch = False, #whether to raise an error if the fids set on the layer dont match the data
                 
                 infer_dtypes = True, #whether to referesh the dtyping in the df
                 
                 logger=mod_logger, db_f=False):
    
    log = logger.getChild('feats_build')
    #===========================================================================
    # precheck
    #===========================================================================
    #geometry input logic
    if (not geo_d is None) and (not geo_fn_tup is None):
        raise Error('todo: implement non geo layers')
    
    #index match
    if isinstance(geo_d, dict):
        #get the data fid_l
        if isinstance(data, pd.DataFrame):
            dfid_l = data.index.tolist()
        elif isinstance(data, dict):
            dfid_l = list(data.keys())
        else:
            raise Error('unexpected type')
        
        if not linr(dfid_l, list(geo_d.keys()),'feat_data', 'geo_d', 
                            sort_values=True, result_type='exact', logger=log):
            raise Error('passed geo_d and data indexes dont match')
    
    #overrides
    if geo_fn_tup: 
        geofn_hits = 0
        sub_field_match = False #dropping geometry fields
    else: 
        sub_field_match = True
        


    log.debug('for %i data type %s'%(
        len(data), type(data)))
    #===========================================================================
    # data conversion
    #===========================================================================
    if isinstance(data, pd.DataFrame):
        
        #check the index (this will be the fids)
        if not data.index.dtype.char == 'q':
            raise Error('expected integer index')
        
        fid_ar = data.index.values
        
        #infer types
        if infer_dtypes:
            data = data.infer_objects()
            
        #convert the data
        qvlayd = df_to_qvlayd(data)
        
        #=======================================================================
        # build fields container from data
        #=======================================================================
        """we need to convert numpy types to pytypes.
            these are later convert to Qtypes"""
        
        fields_d = dict()
        for coln, col in data.items():
            if not geo_fn_tup is None:
                if coln in geo_fn_tup: 
                    geofn_hits +=1
                    continue #skip this one
                
            #set the type for this name
            fields_d[coln] = np_to_pytype(col.dtype, logger=log)
            
        qfields = fields_build_new(fields_d = fields_d, logger=log)
        
        #=======================================================================
        # some checks
        #=======================================================================
        
        
        if db_f:
            #calc hte expectation
            if geo_fn_tup is None:
                exp_cnt= len(data.columns)
            else:
                exp_cnt = len(data.columns) - len(geo_fn_tup)
            
            if not exp_cnt == len(fields_d):
                raise Error('only generated %i fields from %i columns'%(
                    len(data.columns), len(fields_d)))
                
            #check we got them all
            if not exp_cnt == len(qfields):
                raise Error('failed to create all the fields')
        
        """
        for field in qfields:
            print(field)
        
        qfields.toList()
        
        new_qfield = QgsField(fname, qtype, typeName=QMetaType.typeName(QgsField(fname, qtype).type()))
        
        """
        
    else:
        fid_ar = np.array(list(data.keys()))
        #set the data
        qvlayd = data
        
    
        #===========================================================================
        # build fields container from data
        #===========================================================================
        #slice out geometry data if there
        sub_d1 = list(qvlayd.values())[0] #just get the first
        sub_d2 = dict()
        
        
        for fname, value in sub_d1.items():
            if not geo_fn_tup is None:
                if fname in geo_fn_tup: 
                    geofn_hits +=1
                    continue #skip this one
            sub_d2[fname] = value
        
        #build the fields from this sample data
        qfields = fields_build_new(samp_d = sub_d2, logger=log)
        
        
    #check for geometry field names
    if not geo_fn_tup is None:
        if not geofn_hits == len(geo_fn_tup):
            log.error('missing some geometry field names form the data')
            raise IOError
        
        
    #===========================================================================
    # extract geometry
    #===========================================================================
    if geo_d is None:
        #check for nulls
        if db_f:
            chk_df= pd.DataFrame.from_dict(qvlayd, orient='index')
            
            if chk_df.loc[:, geo_fn_tup].isna().any().any():
                raise Error('got some nulls on the geometry fields: %s'%geo_fn_tup)

            
        
        geo_d = dict()
        for fid, sub_d in copy.copy(qvlayd).items():
            #get the xy
            xval, yval = sub_d.pop(geo_fn_tup[0]), sub_d.pop(geo_fn_tup[1])
            
            #build the geometry
            geo_d[fid] = QgsGeometry.fromPointXY(QgsPointXY(xval,yval))
            
            #add the cleaned data back in
            qvlayd[fid] = sub_d
            
    #===========================================================================
    # check geometry
    #===========================================================================
    if db_f:
        #precheck geometry validty
        for fid, geo in geo_d.items():
            if not geo.isGeosValid():
                raise Error('got invalid geometry on %i'%fid)

            
        
    
    #===========================================================================
    # loop through adn build features
    #===========================================================================
    feats_d = dict()
    for fid, sub_d in qvlayd.items():
        #=======================================================================
        # #log.debug('assembling feature %i'%fid)
        # #=======================================================================
        # # assmble geometry data
        # #=======================================================================
        # if isinstance(geo_d, dict):
        #     geo = geo_d[fid]
        #     
        # elif not geo_fn_tup is None:
        #     xval = sub_d[geo_fn_tup[0]]
        #     yval = sub_d[geo_fn_tup[1]]
        #     
        #     if pd.isnull(xval) or pd.isnull(yval):
        #         log.error('got null geometry values')
        #         raise IOError
        #     
        #     geo = QgsGeometry.fromPointXY(QgsPointXY(xval,yval))
        #     #Point(xval, yval) #make the point geometry
        # 
        # else:
        #     geo = None
        #=======================================================================
            
        
        #=======================================================================
        # buidl the feature
        #=======================================================================
        #=======================================================================
        # feats_d[fid] = feat_build(fid, sub_d, qfields=qfields, geometry=geo, 
        #                           sub_field_match = sub_field_match, #because we are excluding the geometry from the fields
        #                           logger=log, db_f=db_f)
        #=======================================================================
        feat = QgsFeature(qfields, fid) 
        
        for fieldn, value in sub_d.items():
            """
            cut out feat_build() for simplicity
            """
        
            #skip null values
            if pd.isnull(value): continue
            
            #get the index for this field
            findx = feat.fieldNameIndex(fieldn) 
            
            #get the qfield
            qfield = feat.fields().at(findx)
            
            #make the type match
            ndata = qtype_to_pytype(value, qfield.type(), logger=log)
            
            #set the attribute
            if not feat.setAttribute(findx, ndata):
                raise Error('failed to setAttribute')
            
            #setgeometry
            feat.setGeometry(geo_d[fid])
            
            #stor eit
            feats_d[fid]=feat
        
        
    #===========================================================================
    # checks
    #===========================================================================
    
    if db_f:
        #fid match
        nfid_ar = np.array(list(feats_d.keys()))
        
        if not np.array_equal(nfid_ar, fid_ar):
            log.warning('fid mismatch')
            
            if not allow_fid_mismatch:
                raise Error('fid mismatch')
            
        #feature validty
        for fid, feat in feats_d.items():
            if not feat.isValid():
                raise Error('invalid feat %i'%feat.id())

            if not feat.geometry().isGeosValid():
                raise Error('got invalid geometry on feat \'%s\''%(feat.id()))
            
            """
            feat.geometry().type()
            
            
            """
            
        
        
    log.debug('built %i \'%s\'  features'%(
        len(feats_d),
        QgsWkbTypes.geometryDisplayString(feat.geometry().type()),
        ))
    
    return feats_d
  
  
def fields_build_new( #build qfields from different data containers
                    samp_d = None, #sample data from which to build qfields {fname: value}
                    fields_d = None, #direct data from which to build qfields {fname: pytype}
                    fields_l = None, #list of QgsField objects
                    logger=mod_logger):

    log = logger.getChild('fields_build_new')
    #===========================================================================
    # buidl the fields_d
    #===========================================================================
    if (fields_d is None) and (fields_l is None): #only if we have nothign better to start with
        if samp_d is None: 
            log.error('got no data to build fields on!')
            raise IOError
        
        fields_l = []
        for fname, value in samp_d.items():
            if pd.isnull(value):
                log.error('for field \'%s\' got null value')
                raise IOError
            
            elif inspect.isclass(value):
                raise IOError
            
            fields_l.append(field_new(fname, pytype=type(value)))
            
        log.debug('built %i fields from sample data'%len(fields_l))
        
    
    
    #===========================================================================
    # buidl the fields set
    #===========================================================================
    elif fields_l is None:
        fields_l = []
        for fname, ftype in fields_d.items():
            fields_l.append(field_new(fname, pytype=ftype))
            
        log.debug('built %i fields from explicit name/type'%len(fields_l))
            
        #check it 
        if not len(fields_l) == len(fields_d):
            raise Error('length mismatch')
            
    elif fields_d is None: #check we have the other
        raise IOError
    
    
    
            
    #===========================================================================
    # build the Qfields
    #===========================================================================
    
    Qfields = QgsFields()
    
    fail_msg_d = dict()
    
    for indx, field in enumerate(fields_l): 
        if not Qfields.append(field):
            fail_msg_d[indx] = ('%i failed to append field \'%s\''%(indx, field.name()), field)

    #report
    if len(fail_msg_d)>0:
        for indx, (msg, field) in fail_msg_d.items():
            log.error(msg)
            
        raise Error('failed to write %i fields'%len(fail_msg_d))
    
    """
    field.name()
    field.constraints().constraintDescription()
    field.length()
    
    """
    
    
    #check it 
    if not len(Qfields) == len(fields_l):
        raise Error('length mismatch')


    return Qfields

def field_new(fname, 
              pytype=str, 
              driverName = 'SpatiaLite', #desired driver (to check for field name length limitations)
              fname_trunc = True, #whether to truncate field names tha texceed the limit
              logger=mod_logger): #build a QgsField
    
    #===========================================================================
    # precheck
    #===========================================================================
    if not isinstance(fname, str):
        raise IOError('expected string for fname')
    
    #vector layer field name lim itation
    max_len = fieldn_max_d[driverName]
    """
    fname = 'somereallylongname'
    """
    if len(fname) >max_len:
        log = logger.getChild('field_new')
        log.warning('got %i (>%i)characters for passed field name \'%s\'. truncating'%(len(fname), max_len, fname))
        
        if fname_trunc:
            fname = fname[:max_len]
        else:
            raise Error('field name too long')
        
    
    qtype = ptype_to_qtype(pytype)
    
    """
    #check this type
    QMetaType.typeName(QgsField(fname, qtype).type())
    
    QVariant.String
    QVariant.Int
    
     QMetaType.typeName(new_qfield.type())
    
    """
    #new_qfield = QgsField(fname, qtype)
    new_qfield = QgsField(fname, qtype, typeName=QMetaType.typeName(QgsField(fname, qtype).type()))
    
    return new_qfield

def vlay_get_bgeo_type(vlay,
                       match_flags=re.IGNORECASE,
                       ):
    
    gstr = QgsWkbTypes().displayString(vlay.wkbType()).lower()
    
    for gtype in ('polygon', 'point', 'line'):
        if re.search(gtype, gstr,  flags=match_flags):
            return gtype
        
    raise Error('failed to match')

#==============================================================================
# type checks-----------------
#==============================================================================

def qisnull(obj):
    if obj is None:
        return True
    
    if isinstance(obj, QVariant):
        if obj.isNull():
            return True
        else:
            return False
        
    
    if pd.isnull(obj):
        return True
    else:
        return False
    
def is_qtype_match(obj, qtype_code, logger=mod_logger): #check if the object matches the qtype code
    log = logger.getChild('is_qtype_match')
    
    #get pythonic type for this code
    try:
        py_type = type_qvar_py_d[qtype_code]
    except:

        if not qtype_code in type_qvar_py_d.keys():
            log.error('passed qtype_code \'%s\' not in dict from \'%s\''%(qtype_code, type(obj)))
            raise IOError
    
    if not isinstance(obj, py_type):
        #log.debug('passed object of type \'%s\' does not match Qvariant.type \'%s\''%(type(obj), QMetaType.typeName(qtype_code)))
        return False
    else:
        return True


#==============================================================================
# type conversions----------------
#==============================================================================

def np_to_pytype(npdobj, logger=mod_logger):
    
    if not isinstance(npdobj, np.dtype):
        raise Error('not passed a numpy type')
    
    try:
        return npc_pytype_d[npdobj.char]

    except Exception as e:
        log = logger.getChild('np_to_pytype')
        
        if not npdobj.char in npc_pytype_d.keys():
            log.error('passed npdtype \'%s\' not found in the conversion dictionary'%npdobj.name)
            
        raise Error('failed oto convert w/ \n    %s'%e)
    

def qtype_to_pytype( #convert object to the pythonic type taht matches the passed qtype code
        obj, 
        qtype_code, #qtupe code (qfield.type())
        logger=mod_logger): 
    
    if is_qtype_match(obj, qtype_code): #no conversion needed
        return obj 
    
    
    #===========================================================================
    # shortcut for nulls
    #===========================================================================
    if qisnull(obj):
        return None

        
    
        
    
    
    #get pythonic type for this code
    py_type = type_qvar_py_d[qtype_code]
    
    try:
        return py_type(obj)
    except:
        #datetime
        if qtype_code == 16:
            return obj.toPyDateTime()
        
        
        log = logger.getChild('qtype_to_pytype')
        if obj is None:
            log.error('got NONE type')
            
        elif isinstance(obj, QVariant):
            log.error('got a Qvariant object')
            
        else:
            log.error('unable to map object \'%s\' of type \'%s\' to type \'%s\''
                      %(obj, type(obj), py_type))
            
            
            """
            QMetaType.typeName(obj)
            """
        raise IOError
    
def ptype_to_qtype(py_type, logger=mod_logger): #get the qtype corresponding to the passed pytype
    """useful for buildign Qt objects
    
    really, this is a reverse 
    
    py_type=str
    
    """
    if not inspect.isclass(py_type):
        logger.error('got unexpected type \'%s\''%type(py_type))
        raise Error('bad type')
    
    #build a QVariant object from this python type class, then return its type
    try:
        qv = QVariant(py_type())
    except:
        logger.error('failed to build QVariant from \'%s\''%type(py_type))
        raise IOError
    
    """
    #get the type
    QMetaType.typeName(qv.type())
    """
    
    
    return qv.type()
        

    
def df_to_qvlayd( #convert a data frame into the layer data structure (keeyd by index)
        df, #data to convert. df index should match fid index
        logger=mod_logger):
    
    log = logger.getChild('df_to_qvlayd')
    
    d = dict() #data dictionary in qgis structure
    
    #prechecks
    if not df.index.is_unique:
        log.error('got passed non-unique index')
        raise IOError
    
    #===========================================================================
    # loop and fill
    #===========================================================================
    for fid, row in df.iterrows():
        
        #=======================================================================
        # build sub data 
        #=======================================================================
        sub_d = dict() #sub data structure
        
        for fieldn, value in row.items():
            sub_d[fieldn] = value
            
        #=======================================================================
        # add the sub into the main
        #=======================================================================
        d[fid] = sub_d
        
    
    if not len(df) == len(d):
        log.error('got length mismatch')
        raise IOError
    
    log.debug('converted df %s into qvlayd'%str(df.shape))
        
    
    
    return d


if __name__ == '__main__':
    print('start')

    
    print('finished')

