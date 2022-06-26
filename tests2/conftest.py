'''
Created on Feb. 21, 2022

@author: cefect

 
'''
import os, shutil, sys, datetime
import pytest
import numpy as np
from numpy.testing import assert_equal
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal, assert_index_equal
 

from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer, QgsWkbTypes, QgsRasterLayer, \
    QgsMapLayer
    
import processing
 

from wFlow.scripts import Session
 

class Session_pytest(Session): #QGIS enabled session handler for testing dialogs
    """see also
    dial_coms.DTestSessionQ
    """
    iface=None
    finv_vlay=None
    def __init__(self, 
                 crs=None,logger=None,
                  **kwargs):
        
        if logger is None:
            """unlike the wflow session, plugin loggers use special methods for interfacing with QGIS"""

            logger= devPlugLogger(self, log_nm='L')
            
            
 
        super().__init__(crsid = crs.authid(), logger=logger, 
                         #feedbac=MyFeedBackQ(logger=logger),
                         **kwargs)  
        
        
 
        self.logger.info('finished Session_pytest.__init__')
        
    def init_dialog(self,
                    DialogClass,
                    ):
        
        self.Dialog = DialogClass(None, session=self, plogger=self.logger)
                    
        self.Dialog.launch()

        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass
        
 
        
         
        #sys.exit(self.qap.exec_()) #wrap
        #sys.exit() #wrap
        print('exiting DialTester')
        
@pytest.fixture(scope='function')
def dialogClass(request): #always passing this as an indirect
    return request.param

@pytest.fixture(scope='function')
def session(tmp_path,
  
            base_dir, 
            write,  # (scope=session)
            crs, dialogClass,
                    
                    ):
 
    np.random.seed(100)
    
    #configure output
    out_dir=tmp_path
    if write:
        #retrieves a directory specific to the test... useful for writing compiled true data
        """this is dying after the yield statement for some reason...."""
        out_dir = os.path.join(base_dir, os.path.basename(tmp_path))
 
    
    with Session_pytest( 
                 name='test', #probably a better way to propagate through this key
   
                 out_dir=out_dir, 
                 temp_dir=os.path.join(tmp_path, 'temp'),
 
                 crs=crs,
                 
 
                 
                   overwrite=True,
                   write=write, #avoid writing prep layers
  
        ) as ses:
        
        ses.init_dialog(dialogClass)
 
        yield ses

@pytest.fixture(scope='session')
def write():
    #===========================================================================
    # write key
    #===========================================================================
    write=False
    #===========================================================================
    # write key
    #===========================================================================
    
    if write:
        print('WARNING!!! runnig in write mode')
    return write

#===============================================================================
# function.fixtures-------
#===============================================================================
 
 
#===============================================================================
# session.fixtures----------
#===============================================================================
 
#===============================================================================
# logger
#===============================================================================
from hlpr.plug import plugLogger
from hlpr.logr import basic_logger
mod_logger = basic_logger()

class devPlugLogger(plugLogger):
    """wrapper to overwriting Qspecific methods with python logging"""
 
    def getChild(self, new_childnm):
        
 
        log_nm = '%s.%s'%(self.log_nm, new_childnm)
        
        #build a new logger
        child_log = devPlugLogger(self.parent,log_nm=log_nm)
 
        return child_log
        
          
    
    def _loghlp(self, #helper function for generalized logging
                msg_raw, qlevel, 
                push=False, #treat as a push message on Qgis' bar
                status=False, #whether to send to the status widget
                ):
        
        #=======================================================================
        # send message based on qlevel
        #=======================================================================
        msgDebug = '%s    %s: %s'%(datetime.datetime.now().strftime('%d-%H.%M.%S'), self.log_nm,  msg_raw)
        if qlevel < 0: #file logger only
            
            mod_logger.debug('D_%s'%msgDebug)
            push, status = False, False #should never trip
        else:#console logger
            msg = '%s:   %s'%(self.log_nm, msg_raw)
            mod_logger.info(msg)
 
        
        #Qgis bar
        if push:
            print('PUSH: ' +msg_raw)
            
 
 

@pytest.fixture(scope='session')
def base_dir():
 
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
 
    assert os.path.exists(base_dir), base_dir
    return base_dir



@pytest.fixture
def true_dir(write, tmp_path, base_dir):
    true_dir = os.path.join(base_dir, os.path.basename(tmp_path))
    if write:
        if os.path.exists(true_dir):
            try: 
                shutil.rmtree(true_dir)
                os.makedirs(true_dir) #add back an empty folder
                os.makedirs(os.path.join(true_dir, 'working')) #and the working folder
            except Exception as e:
                print('failed to cleanup the true_dir: %s w/ \n    %s'%(true_dir, e))

            
    return true_dir
    
#===============================================================================
# helper funcs-------
#===============================================================================
def search_fp(dirpath, ext, pattern): #get a matching file with extension and beginning
    assert os.path.exists(dirpath), 'searchpath does not exist: %s'%dirpath
    fns = [e for e in os.listdir(dirpath) if e.endswith(ext)]
    
    result= None
    for fn in fns:
        if pattern in fn:
            result = os.path.join(dirpath, fn)
            break
        
    if result is None:
        raise IOError('failed to find a match for \'%s\' in %s'%(pattern, dirpath))
    
    assert os.path.exists(result), result
        
        
    return result


def retrieve_data(dkey, fp, ses): #load some compiled result off the session (using the dkey)
    assert dkey in ses.data_retrieve_hndls
    hndl_d = ses.data_retrieve_hndls[dkey]
    assert 'compiled' in hndl_d, '%s has no compliled handles'%dkey
    
    return hndl_d['compiled'](fp=fp, dkey=dkey)

 
            
def rasterstats(rlay): 
      
    ins_d = { 'BAND' : 1, 
             'INPUT' : rlay,
              'OUTPUT_HTML_FILE' : 'TEMPORARY_OUTPUT' }
 
    return processing.run('native:rasterlayerstatistics', ins_d )   
            
            
            
            
            
            
            
            
