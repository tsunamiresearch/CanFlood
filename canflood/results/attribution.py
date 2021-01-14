'''
Created on Feb. 9, 2020

@author: cefect

attribution analysis
'''

#==========================================================================
# logger setup-----------------------
#==========================================================================
import logging, configparser, datetime, copy

from weakref import WeakValueDictionary as wdict

#==============================================================================
# imports------------
#==============================================================================
import os
import numpy as np
import pandas as pd
from pandas import IndexSlice as idx




from hlpr.exceptions import QError as Error
    




#===============================================================================
# non-Qgis
#===============================================================================
from model.modcom import Model
from hlpr.basic import view

#==============================================================================
# functions-------------------
#==============================================================================
class Attr(Model):
    
    #===========================================================================
    # program vars
    #===========================================================================
    """todo: fix this"""
    valid_par='risk2' 
    attrdtag_in = 'attrimat03'
    #===========================================================================
    # expectations from parameter file
    #===========================================================================
    exp_pars_md = {
        'results_fps':{
             'attrimat03':{'ext':('.csv',)},
             'r2_ttl':{'ext':('.csv',)},
             'r2_passet':{'ext':('.csv',)},
             }
        }
    
    exp_pars_op=dict()
 
    


    def __init__(self,
                 cf_fp,

                  *args, **kwargs):
        
        super().__init__(cf_fp, *args, **kwargs)
        

        
        self.logger.debug('%s.__init__ w/ feedback \'%s\''%(
            self.__class__.__name__, type(self.feedback).__name__))
        
    def _setup(self):
        log = self.logger.getChild('setup')
        self.init_model()
        
        self.load_ttl()
        self.load_passet()
        
        self.load_attrimat(dxcol_lvls=3)
        
        #=======================================================================
        # post fix attrim
        #=======================================================================
        #reformat aep values
        atr_dxcol = self.data_d.pop(self.attrdtag_in)
        mdex = atr_dxcol.columns
        atr_dxcol.columns = mdex.set_levels(mdex.levels[0].astype(np.float), level=0)
        self.data_d[self.attrdtag_in] = atr_dxcol
        
        
        #=======================================================================
        # check
        #=======================================================================
        miss_l = set(atr_dxcol.columns.levels[0]).symmetric_difference(self.data_d['r2_passet'].columns)
        assert len(miss_l)==0, 'event mismatch'
        
        #=======================================================================
        # get TOTAL multiplied values
        #=======================================================================
        self.mula_dxcol = self.get_mult(self.data_d[self.attrdtag_in].copy(), logger=log)
 
        
        return self
        
    def load_ttl(self,
                   fp = None,
                   dtag = 'r2_ttl',

                   logger=None,
                    
                    ):
        #=======================================================================
        # defaults
        #=======================================================================
        if logger is None: logger=self.logger
        
        log = logger.getChild('load_ttl')
        if fp is None: fp = getattr(self, dtag)
 
        
        
        #======================================================================
        # load it
        #======================================================================
        df_raw = pd.read_csv(fp, index_col=None)
        self.data_d[dtag] = df_raw.copy()
        #=======================================================================
        # clean
        #=======================================================================
        df = df_raw.drop('plot', axis=1)
        
        #drop EAD row
        boolidx = df['aep']=='ead'
        df = df.loc[~boolidx, :]
        df.loc[:, 'aep'] = df['aep'].astype(np.float)
        
        #drop extraploated
        boolidx = df['note']=='extraploated'
        df = df.loc[~boolidx, :].drop('note', axis=1)
        #=======================================================================
        # set it
        #=======================================================================
        self.eventNames = df['aep'].values
        
        self.data_d['ttl'] = df
        
    def load_passet(self, #load the per-asset results
                   fp = None,
                   dtag = 'r2_passet',

                   logger=None,
                    
                    ):
        #=======================================================================
        # defa8ults
        #=======================================================================
        if logger is None: logger=self.logger
        
        log = logger.getChild('load_passet')
        if fp is None: fp = getattr(self, dtag)
        cid = self.cid
        
        #======================================================================
        # load it
        #======================================================================
        df_raw = pd.read_csv(fp, index_col=0)
        
        #drop ead and format column
        df = df_raw.drop('ead', axis=1)
        df.columns = df.columns.astype(np.float)
        
        #drop extraploators and ead
        boolcol = df.columns.isin(self.eventNames)
        df = df.loc[:, boolcol].sort_index(axis=1, ascending=True)
        
        
        #=======================================================================
        # set it
        #=======================================================================
        self.cindex = df.index.copy() #set this for checks later
        self.data_d[dtag] = df
            
    def get_slice(self,
                  lvals_d, #mdex lvl values {lvlName:(lvlval1, lvlval2...)}
                  atr_dxcol=None,
                  logger=None,
                  ):
        
        #=======================================================================
        # defaults
        #=======================================================================
        if logger is  None: logger=self.logger
        if atr_dxcol is None: atr_dxcol=self.data_d[self.attrdtag_in].copy()
        log=logger.getChild('get_slice')
        
        mdex = atr_dxcol.columns
        """
        view(mdex.to_frame())
        """
        nameRank_d= {lvlName:i for i, lvlName in enumerate(mdex.names)}
        rankName_d= {i:lvlName for i, lvlName in enumerate(mdex.names)}
        #=======================================================================
        # precheck
        #=======================================================================
        #quick check on the names
        miss_l = set(lvals_d.keys()).difference(mdex.names)
        assert len(miss_l)==0, '%i requested lvlNames not on mdex: %s'%(len(miss_l), miss_l)
        
        #chekc values
        for lvlName, lvals in lvals_d.items():
            
            #chekc all these are in there
            miss_l = set(lvals).difference(mdex.levels[nameRank_d[lvlName]])
            assert len(miss_l)==0, '%i requsted lvals on \"%s\' not in mdex: %s'%(len(miss_l), lvlName, miss_l)
            

        #=======================================================================
        # get slice            
        #=======================================================================
        log.info('from %i levels on %s'%(len(lvals_d), str(atr_dxcol.shape)))
        """
        s_dxcol = atr_dxcol.loc[:, idx[:, lvals_d['rEventName'], :]].columns.to_frame())
        """
        
        
        """seems like there should be a better way to do this...
        could force the user to pass request with all levels complete"""
        s_dxcol = atr_dxcol.copy()
        #populate missing elements
        for lvlName, lRank  in nameRank_d.items():
            if not lvlName in lvals_d: continue 
            
            if lRank == 0: continue #always keeping this
            elif lRank == 1:
                s_dxcol = s_dxcol.loc[:, idx[:, lvals_d[lvlName]]]
            elif lRank == 2:
                s_dxcol = s_dxcol.loc[:, idx[:, :, lvals_d[lvlName]]]
            else:
                raise Error
                
 
        log.info('sliced  to %s'%str(s_dxcol.shape))
        
        return s_dxcol

    def get_mult(self, #multiply dxcol by the asset event totals
                atr_dxcol,
                logger=None,
 
                ): 
        #=======================================================================
        # defaults
        #=======================================================================
        if logger is None: logger=self.logger
        log=logger.getChild('get_ttl')
        rp_df = self.data_d['r2_passet'].copy()
        
        #=======================================================================
        # precheck
        #=======================================================================
        #aep set
        miss_l = set(rp_df.columns).difference(atr_dxcol.columns.levels[0])
        assert len(miss_l)==0, 'event mismatch'
        
        #attribute matrix logic
        """note we accept slices... so sum=1 wont always hold"""
        assert atr_dxcol.notna().all().all()
        assert (atr_dxcol.max()<=1.0).all().all()
        assert (atr_dxcol.max()>=0.0).all().all()
        for e in atr_dxcol.dtypes.values: assert e==np.dtype(float)
        #=======================================================================
        # multiply
        #=======================================================================
        return atr_dxcol.multiply(rp_df, level='aeps')
    
    def get_ttl(self, #get a total impacts summary from an impacts dxcol 
                i_dxcol, #impacts (not attribution ratios)
                ):

        return i_dxcol.sum(axis=1, level='aeps').sum(axis=0).rename('impacts').reset_index(drop=False)
        

    
    def plot(self): #plot slice against original risk c urve
        
        pass
        
        
        
        
        
        
        
        
        
        
        
            