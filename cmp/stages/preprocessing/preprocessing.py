# Copyright (C) 2009-2015, Ecole Polytechnique Federale de Lausanne (EPFL) and
# Hospital Center and University of Lausanne (UNIL-CHUV), Switzerland
# All rights reserved.
#
#  This software is distributed under the open-source license Modified BSD.

""" CMP preprocessing Stage (not used yet!)
""" 

from traits.api import *
from traitsui.api import *

from nipype.interfaces.base import traits, BaseInterface, BaseInterfaceInputSpec, CommandLineInputSpec, CommandLine, OutputMultiPath, TraitedSpec, Interface, InterfaceResult, isdefined
import nipype.interfaces.utility as util

from cmp.stages.common import Stage

import os
import pickle
import gzip

import nipype.pipeline.engine as pe
import nipype.pipeline as pip
import nipype.interfaces.fsl as fsl
import nipype.interfaces.utility as util
import nipype.interfaces.mrtrix as mrt
import nipype.interfaces.ants as ants

import nibabel as nib

# from cmp.pipelines.common import MRThreshold, ExtractMRTrixGrad
from cmp.interfaces.mrtrix3 import DWIDenoise, DWIBiasCorrect, MRConvert, MRThreshold, ExtractFSLGrad, ExtractMRTrixGrad
import cmp.interfaces.fsl as cmp_fsl

from nipype.interfaces.mrtrix3.preprocess import ResponseSD

# class MRTrixInfoInputSpec(CommandLineInputSpec):
#     in_file = File(exists=True, argstr='%s', mandatory=True, position=-2,
#         desc='Input images to be read')
#     _xor_inputs = ('out_grad_mrtrix','out_grad_fsl')
#     out_grad_mrtrix = File(argstr='-export_grad_mrtrix %s',desc='export the DWI gradient table to file in MRtrix format',xor=_xor_inputs)
#     out_grad_fsl =  traits.Tuple(File(),File(), argstr='-export_grad_fsl %s %s', desc='export the DWI gradient table to files in FSL (bvecs / bvals) format', xor=_xor_inputs)

# class MRTrixInfoOutputSpec(TraitedSpec):
#     out_grad_mrtrix = traits.Tuple(File(exists=True),File(exists=True), desc='Outputs [bvecs, bvals] DW gradient scheme (FSL format) if set')
#     out_grad_fsl = File(exits=True,desc='Output MRtrix gradient text file if set')

# class MRTrixInfo(CommandLine):
#     """
#     Prints out relevant header information found in the image specified.

#     Example
#     -------

#     >>> import nipype.interfaces.mrtrix as mrt
#     >>> MRinfo = mrt.MRTrixInfo()
#     >>> MRinfo.inputs.in_file = 'dwi.mif'
#     >>> MRinfo.run()                                    # doctest: +SKIP
#     """

#     _cmd = 'mrinfo'
#     input_spec=MRTrixInfoInputSpec
#     output_spec=MRTrixInfoOutputSpec

#     def _list_outputs(self):
#         outputs = self.output_spec().get()
#         outputs['out_grad_mrtrix'] = op.abspath(self.inputs.out_grad_mrtrix)
#         if isdefined(self.inputs.out_grad_mrtrix):
#             outputs['out_grad_mrtrix'] = op.abspath(self.inputs.out_grad_mrtrix)
#         if isdefined(self.inputs.out_grad_fsl):
#             outputs['out_grad_fsl'] = (op.abspath(self.inputs.out_grad_fsl[0]),op.abspath(self.inputs.out_grad_mrtrix[1]))
#         return outputs

class splitDiffusion_InputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True)
    start = Int(0)
    end = Int()
    
class splitDiffusion_OutputSpec(TraitedSpec):
    data = File(exists=True)
    padding1 = File(exists=False)
    padding2 = File(exists=False)
    
class splitDiffusion(BaseInterface):
    input_spec = splitDiffusion_InputSpec
    output_spec = splitDiffusion_OutputSpec
    
    def _run_interface(self,runtime):
        diffusion_file = nib.load(self.inputs.in_file)
        diffusion = diffusion_file.get_data()
        affine = diffusion_file.get_affine()
        dim = diffusion.shape
        if self.inputs.start > 0 and self.inputs.end > dim[3]-1:
            error('End volume is set to %d but it should be bellow %d' % (self.inputs.end, dim[3]-1))
        padding_idx1 = range(0,self.inputs.start)
        if len(padding_idx1) > 0:
            temp = diffusion[:,:,:,0:self.inputs.start]
            nib.save(nib.nifti1.Nifti1Image(temp,affine),os.path.abspath('padding1.nii.gz'))
        temp = diffusion[:,:,:,self.inputs.start:self.inputs.end+1]
        nib.save(nib.nifti1.Nifti1Image(temp,affine),os.path.abspath('data.nii.gz'))
        padding_idx2 = range(self.inputs.end,dim[3]-1)
        if len(padding_idx2) > 0:
            temp = diffusion[:,:,:,self.inputs.end+1:dim[3]]
            nib.save(nib.nifti1.Nifti1Image(temp,affine),os.path.abspath('padding2.nii.gz'))        
            
        return runtime
    
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["data"] = os.path.abspath('data.nii.gz')
        if os.path.exists(os.path.abspath('padding1.nii.gz')):
            outputs["padding1"] = os.path.abspath('padding1.nii.gz')
        if os.path.exists(os.path.abspath('padding2.nii.gz')):
            outputs["padding2"] = os.path.abspath('padding2.nii.gz')
        return outputs

# class ConcatOutputsAsTuple(Interface):
#     """join two inputs into a tuple
#     """
#     def __init__(self, *args, **inputs):
#         self._populate_inputs()

#     def _populate_inputs(self):
#         self.inputs = Bunch(input1=None,
#                             input2=None)

#     def get_input_info(self):
#         return []

#     def outputs(self):
#         return Bunch(output=None)

#     def aggregate_outputs(self):
#         outputs = self.outputs()
#         outputs.output =  (self.inputs.input1,self.inputs.input2)
#         # if isinstance(self.inputs.input1,str) and isinstance(self.inputs.input2,str):
#         #     outputs.output =  (self.inputs.input1,self.inputs.input2)
#         # else:
#         #     outputs.output.extend(self.inputs.input2)
#         return outputs

#     def run(self, cwd=None):
#         """Execute this module.
#         """
#         runtime = Bunch(returncode=0,
#                         stdout=None,
#                         stderr=None)
#         outputs=self.aggregate_outputs()
#         return InterfaceResult(deepcopy(self), runtime, outputs=outputs)
class CreateAcqpFileInputSpec(BaseInterfaceInputSpec):
    total_readout = Float(0.0)

class CreateAcqpFileOutputSpec(TraitedSpec):
    acqp = File(exists=True)

class CreateAcqpFile(BaseInterface):
    input_spec = CreateAcqpFileInputSpec
    output_spec = CreateAcqpFileOutputSpec

    def _run_interface(self,runtime):
        import numpy as np

        # Matrix giving phase-encoding direction (3 first columns) and total read out time (4th column)
        # For phase encoding A << P <=> y-direction
        # Total readout time = Echo spacing x EPI factor x 0.001 [s]
        mat = np.array([['0','1','0',str(self.inputs.total_readout)],
                        ['0','-1','0',str(self.inputs.total_readout)]])

        out_f = file(os.path.abspath('acqp.txt'),'a')
        np.savetxt(out_f,mat,fmt="%s",delimiter=' ')
        out_f.close()
        return runtime
    
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["acqp"] = os.path.abspath('acqp.txt')
        return outputs

class CreateIndexFileInputSpec(BaseInterfaceInputSpec):
    in_grad_mrtrix = File(exists=True,mandatory=True,desc='Input DWI gradient table in MRTric format')
class CreateIndexFileOutputSpec(TraitedSpec):
    index = File(exists=True)

class CreateIndexFile(BaseInterface):
    input_spec = CreateIndexFileInputSpec
    output_spec = CreateIndexFileOutputSpec

    def _run_interface(self,runtime):
        axis_dict = {'x':0, 'y':1, 'z':2}
        import numpy as np

        with open(self.inputs.in_grad_mrtrix,'r') as f:
            for i, l in enumerate(f):
                pass

        lines = i+1

        mat = np.ones((1,lines))

        out_f = file(os.path.abspath('index.txt'),'a')
        np.savetxt(out_f,mat,delimiter=' ',fmt="%1.0g")
        out_f.close()
        return runtime
    
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["index"] = os.path.abspath('index.txt')
        return outputs

class ConcatOutputsAsTupleInputSpec(BaseInterfaceInputSpec):
    input1 = File(exists=True)
    input2 = File(exists=True)
    
class ConcatOutputsAsTupleOutputSpec(TraitedSpec):
    out_tuple = traits.Tuple(File(exists=True),File(exists=True))

class ConcatOutputsAsTuple(BaseInterface):
    input_spec = ConcatOutputsAsTupleInputSpec
    output_spec = ConcatOutputsAsTupleOutputSpec
    
    def _run_interface(self,runtime):
        self._outputs().out_tuple = (self.inputs.input1,self.inputs.input2)
        return runtime
    
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["out_tuple"] = (self.inputs.input1,self.inputs.input2)
        return outputs


class flipTableInputSpec(BaseInterfaceInputSpec):
    table = File(exists=True)
    flipping_axis = List()
    delimiter = Str()
    header_lines = Int(0)
    orientation = Enum(['v','h'])
    
class flipTableOutputSpec(TraitedSpec):
    table = File(exists=True)

class flipTable(BaseInterface):
    input_spec = flipTableInputSpec
    output_spec = flipTableOutputSpec
    
    def _run_interface(self,runtime):
        axis_dict = {'x':0, 'y':1, 'z':2}
        import numpy as np
        f = open(self.inputs.table,'r')
        header = ''
        for h in range(self.inputs.header_lines):
            header += f.readline()
        if self.inputs.delimiter == ' ':
            table = np.loadtxt(f)
        else:
            table = np.loadtxt(f, delimiter=self.inputs.delimiter)
        f.close()
        if self.inputs.orientation == 'v':
            for i in self.inputs.flipping_axis:
                table[:,axis_dict[i]] = -table[:,axis_dict[i]]
        elif self.inputs.orientation == 'h':
            for i in self.inputs.flipping_axis:
                table[axis_dict[i],:] = -table[axis_dict[i],:]
        out_f = file(os.path.abspath('flipped_table.txt'),'a')
        if self.inputs.header_lines > 0:
            out_f.write(header)
        np.savetxt(out_f,table,delimiter=self.inputs.delimiter)
        out_f.close()
        return runtime
    
    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["table"] = os.path.abspath('flipped_table.txt')
        return outputs

class PreprocessingConfig(HasTraits):
    total_readout = Float(0.0)
    description = Str('description')
    denoising = Bool(False)
    bias_field_correction = Bool(False)
    bias_field_algo = Enum('ANTS N4',['ANTS N4','FSL FAST'])
    eddy_current_and_motion_correction = Bool(False)
    start_vol = Int(0)
    end_vol = Int()
    max_vol = Int()
    max_str = Str
    traits_view = View( Item('denoising'),
                        HGroup(
                            Item('bias_field_correction'),
                            Item('bias_field_algo',label='Tool:',visible_when='bias_field_correction==True')
                            ),
                        HGroup(
                            Item('eddy_current_and_motion_correction'),
                            Item('total_readout',label='Total readout time (s):',visible_when='eddy_current_and_motion_correction==True')
                            ),
                        HGroup(
                            Item('start_vol',label='Vol'),
                            Item('end_vol',label='to'),
                            Item('max_str',style='readonly',show_label=False)
                            )
                        )
    
    def _max_vol_changed(self,new):
        self.max_str = '(max: %d)' % new
        
    def _end_vol_changed(self,new):
        if new > self.max_vol:
            self.end_vol = self.max_vol
            
    def _start_vol_changed(self,new):
        if new < 0:
            self.start_vol = 0

class PreprocessingStage(Stage):
    # General and UI members
    def __init__(self):
        self.name = 'preprocessing_stage'
        self.config = PreprocessingConfig()
        self.inputs = ["diffusion","bvecs","bvals","T1","brain","brain_mask","wm_mask_file","roi_volumes"]
        self.outputs = ["diffusion_preproc","bvecs_rot","dwi_brain_mask","T1","brain","brain_mask","brain_mask_full","wm_mask_file","roi_volumes"]
    
    def create_workflow(self, flow, inputnode, outputnode):
        print inputnode
        processing_input = pe.Node(interface=util.IdentityInterface(fields=['diffusion','bvecs','bvals','grad','acqp','index','T1','brain','brain_mask','wm_mask_file','roi_volumes']),name='processing_input')
        

        # For DSI acquisition: extract the hemisphere that contains the data
        if self.config.start_vol > 0 or self.config.end_vol < self.config.max_vol:
            split_vol = pe.Node(interface=splitDiffusion(),name='split_vol')
            split_vol.inputs.start = self.config.start_vol
            split_vol.inputs.end = self.config.end_vol
            flow.connect([
                        (inputnode,split_vol,[('diffusion','in_file')]),
                        (split_vol,processing_input,[('data','diffusion')]),
                        (inputnode,processing_input,[('T1','T1'),('brain','brain'),('brain_mask','brain_mask'),('bvecs','bvecs'),('bvals','bvals'),('wm_mask_file','wm_mask_file'),('roi_volumes','roi_volumes')])
                        ])
        else:
            flow.connect([
                        (inputnode,processing_input,[('diffusion','diffusion'),('bvecs','bvecs'),('bvals','bvals'),('T1','T1'),('brain','brain'),('brain_mask','brain_mask'),('wm_mask_file','wm_mask_file'),('roi_volumes','roi_volumes')]),
                        ])
        print inputnode.inputs
        #TODO: Add denoising (DWdenoise)/ bias field correction (FSL FIRST)/ New registration: FSL FLIRT and FNIRT (if no top up), SPM rigid coregistration (if topup)
        # if self.config.denoising:
        #     dwi_denoise = pe.Node(interface=mrt.DWIDenoise() , name='dwi_denoise')
        #     flow.connect([
        #                 (processing_input,dwi_denoise,[("diffusion","in_file")])
        #                 ])
        
        # Flip gradient table
        # flip_table = pe.Node(interface=flipTable(),name='flip_table')
        # flip_table.inputs.table = self.config.gradient_table
        # flip_table.inputs.flipping_axis = self.config.flip_table_axis
        # flip_table.inputs.delimiter = ' '
        # flip_table.inputs.header_lines = 0
        # flip_table.inputs.orientation = 'v'
        # flow.connect([
        #         (flip_table,processing_input,[("table","grad")]),
        #         ])

        #Computes brain mask using FSL BET
        # Swap dimensions so stuff looks nice in the report
        #flipbrain2fsl = pe.Node(interface=fsl.SwapDimensions(new_dims=("RL","PA","IS")),name="flipbrain2fsl")
        #bet = pe.Node(interface=fsl.BET(out_file='brain.nii.gz'), name='bet')
        #bet.inputs.mask = True
        #bet.inputs.frac = 0.5

        #flipbrain2mrtrix

        #Conversion to MRTrix image format ".mif", grad_fsl=(inputnode.inputs.bvecs,inputnode.inputs.bvals)
        mr_convert = pe.Node(interface=MRConvert(out_filename='diffusion.mif',stride=[-1,-2,+3,+4]), name='mr_convert')
        mr_convert.inputs.quiet = True
        mr_convert.inputs.force_writing = True

        concatnode = pe.Node(interface=util.Merge(2),name='concatnode')
        
        def convertList2Tuple(lists):
            print "******************************************",tuple(lists)
            return tuple(lists)

        flow.connect([
            # (processing_input,concatnode,[('bvecs','in1'),('bvals','in2')]),
            (processing_input,concatnode,[('bvecs','in1')]),
            (processing_input,concatnode,[('bvals','in2')]),
            (concatnode,mr_convert,[(('out',convertList2Tuple),'grad_fsl')]),
            (processing_input,mr_convert,[('diffusion','in_file')])
            ])

        #Convert Freesurfer data
        mr_convert_brainmask = pe.Node(interface=MRConvert(out_filename='brainmaskfull.nii.gz',stride=[-1,2,3],output_datatype='float32'),name='mr_convert_brain_mask')
        mr_convert_brain = pe.Node(interface=MRConvert(out_filename='anat_masked.nii.gz',stride=[-1,2,3],output_datatype='float32'),name='mr_convert_brain')
        mr_convert_T1 = pe.Node(interface=MRConvert(out_filename='anat.nii.gz',stride=[-1,2,3],output_datatype='float32'),name='mr_convert_T1')
        mr_convert_roi_volumes = pe.Node(interface=MRConvert(out_filename='roi_volumes.nii.gz',stride=[-1,2,3],output_datatype='float32'),name='mr_convert_roi_volumes')
        mr_convert_wm_mask_file = pe.Node(interface=MRConvert(out_filename='wm_mask_file.nii.gz',stride=[-1,2,3],output_datatype='float32'),name='mr_convert_wm_mask_file')

        flow.connect([
                    (processing_input,mr_convert_brainmask,[('brain_mask','in_file')]),
                    (processing_input,mr_convert_brain,[('brain','in_file')]),
                    (processing_input,mr_convert_T1,[('T1','in_file')]),
                    (processing_input,mr_convert_roi_volumes,[('roi_volumes','in_file')]),
                    (processing_input,mr_convert_wm_mask_file,[('wm_mask_file','in_file')])
                    ])

        flow.connect([
                    (mr_convert_brainmask,outputnode,[('converted','brain_mask_full')]),
                    (mr_convert_brain,outputnode,[('converted','brain')]),
                    (mr_convert_T1,outputnode,[('converted','T1')]),
                    (mr_convert_roi_volumes,outputnode,[('converted','roi_volumes')]),
                    (mr_convert_wm_mask_file,outputnode,[('converted','wm_mask_file')])
                    ])

        #Threshold converted Freesurfer brainmask into a binary mask
        mr_threshold_brainmask = pe.Node(interface=MRThreshold(abs_value=1,out_file='brain_mask.nii.gz'),name='mr_threshold_brainmask')

        flow.connect([
                    (mr_convert_brainmask,mr_threshold_brainmask,[('converted','in_file')]),
                    (mr_threshold_brainmask,outputnode,[('thresholded','brain_mask')])
                    ])

        #Diffusion data denoising        
        if self.config.denoising:
            dwi_denoise = pe.Node(interface=DWIDenoise(out_file='diffusion_denoised.mif',out_noisemap='diffusion_noisemap.mif') , name='dwi_denoise')
            dwi_denoise.inputs.force_writing = True
            dwi_denoise.inputs.debug = True
            dwi_denoise.ignore_exception = True

            flow.connect([
                (mr_convert,dwi_denoise,[('converted','in_file')])
                ])

        #Extract b0 and create DWI mask
        flirt_dwimask_pre = pe.Node(interface=fsl.FLIRT(out_file='brain2b0.nii.gz',out_matrix_file='brain2b0aff'), name='flirt_dwimask_pre')
        costs=['mutualinfo','corratio','normcorr','normmi','leastsq','labeldiff','bbr']
        flirt_dwimask_pre.inputs.cost=costs[3]
        flirt_dwimask_pre.inputs.cost_func=costs[3]
        flirt_dwimask_pre.inputs.dof=6
        flirt_dwimask_pre.inputs.no_search=False

        flirt_dwimask = pe.Node(interface=fsl.FLIRT(out_file='dwi_brain_mask.nii.gz', apply_xfm = True, interp='nearestneighbour'), name='flirt_dwimask')

        mr_convert_b0 = pe.Node(interface=MRConvert(out_filename='b0.nii.gz',stride=[-1,-2,+3]), name='mr_convert_b0')
        mr_convert_b0.inputs.extract_at_axis = 3
        mr_convert_b0.inputs.extract_at_coordinate = [0.0]

        if self.config.denoising:
            flow.connect([
            (dwi_denoise,mr_convert_b0,[('out_file','in_file')])
            ])

        else:
            flow.connect([
            (processing_input,mr_convert_b0,[('diffusion','in_file')])
            ])

        flow.connect([
            (mr_convert_T1,flirt_dwimask_pre,[('converted','in_file')]),
            (mr_convert_b0,flirt_dwimask_pre,[('converted','reference')]),
            (mr_convert_b0,flirt_dwimask,[('converted','reference')]),
            (flirt_dwimask_pre,flirt_dwimask,[('out_matrix_file','in_matrix_file')]),
            (mr_threshold_brainmask,flirt_dwimask,[('thresholded','in_file')])
            ])

        flow.connect([
                    (flirt_dwimask,outputnode,[('out_file','dwi_brain_mask')])
                    ])


        mr_convert_b = pe.Node(interface=MRConvert(out_filename='diffusion_corrected.nii.gz',stride=[-1,-2,+3,+4]),name='mr_convert_b')
       
        if self.config.bias_field_correction:
            if self.config.bias_field_algo == "ANTS N4":
                dwi_biascorrect = pe.Node(interface=DWIBiasCorrect(use_ants=True,out_bias='diffusion_denoised_biasfield.mif'), name='dwi_biascorrect')
            elif self.config.bias_field_algo == "FSL FAST":
                dwi_biascorrect = pe.Node(interface=DWIBiasCorrect(use_fsl=True,out_bias='diffusion_denoised_biasfield.mif'), name='dwi_biascorrect')

            dwi_biascorrect.inputs.verbose = True

            if self.config.denoising:
                flow.connect([
                    (dwi_denoise,dwi_biascorrect,[('out_file','in_file')]),
                    (flirt_dwimask,dwi_biascorrect,[('out_file','mask')]),
                    (dwi_biascorrect,mr_convert_b,[('out_file','in_file')])
                    ])
            else:
                flow.connect([
                    (mr_convert,dwi_biascorrect,[('converted','in_file')]),
                    (flirt_dwimask,dwi_biascorrect,[('out_file','mask')])
                    ])
        else:
            if self.config.denoising:
                flow.connect([
                    (dwi_denoise,mr_convert_b,[('out_file','in_file')])
                    ])
            else:
                flow.connect([
                    (mr_convert,mr_convert_b,[('converted','in_file')])
                    ])

        extract_grad_mrtrix = pe.Node(interface=ExtractMRTrixGrad(out_grad_mrtrix='grad.txt'),name='extract_grad_mrtrix')
        flow.connect([
            (mr_convert,extract_grad_mrtrix,[("converted","in_file")])
            ])
        #extract_grad_fsl = pe.Node(interface=mrt.MRTrixInfo(out_grad_mrtrix=('diffusion_denoised.bvec','diffusion_denoised.bval')),name='extract_grad_fsl')

        acqpnode = pe.Node(interface=CreateAcqpFile(total_readout=self.config.total_readout),name='acqpnode') 


        indexnode = pe.Node(interface=CreateIndexFile(),name='indexnode')
        flow.connect([
            (extract_grad_mrtrix,indexnode,[("out_grad_mrtrix","in_grad_mrtrix")])
            ])

        if self.config.eddy_current_and_motion_correction:
            eddy_correct = pe.Node(interface=cmp_fsl.EddyOpenMP(out_file="eddy_corrected.nii.gz",verbose=True),name='eddy')
            flow.connect([
                        (mr_convert_b,eddy_correct,[("converted","in_file")]),
                        (processing_input,eddy_correct,[("bvecs","bvecs")]),
                        (processing_input,eddy_correct,[("bvals","bvals")]),
                        (flirt_dwimask,eddy_correct,[("out_file","mask")]),
                        (indexnode,eddy_correct,[("index","index")]),
                        (acqpnode,eddy_correct,[("acqp","acqp")])
                        ])

            flow.connect([
                        (eddy_correct,outputnode,[("bvecs_rotated","bvecs_rot")])
                        ])

            if self.config.start_vol > 0 and self.config.end_vol == self.config.max_vol:
                merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
                flow.connect([
                            (split_vol,merge_filenames,[("padding1","in1")]),
                            (eddy_correct,merge_filenames,[("eddy_corrected","in1")])
                            ])
                merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
                flow.connect([
                            (merge_filenames,merge,[("out","in_files")]),
                            (merge,outputnode,[("merged_file","diffusion_preproc")])
                            ])
            elif self.config.start_vol > 0 and self.config.end_vol < self.config.max_vol:
                merge_filenames = pe.Node(interface=util.Merge(3),name='merge_files')
                flow.connect([
                            (split_vol,merge_filenames,[("padding1","in1")]),
                            (eddy_correct,merge_filenames,[("eddy_corrected","in1")]),
                            (split_vol,merge_filenames,[("padding2","in3")])
                            ])
                merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
                flow.connect([
                            (merge_filenames,merge,[("out","in_files")]),
                            (merge,outputnode,[("merged_file","diffusion_preproc")])
                            ])
            elif self.config.start_vol == 0 and self.config.end_vol < self.config.max_vol:
                merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
                flow.connect([
                            (eddy_correct,merge_filenames,[("eddy_corrected","in1")]),
                            (split_vol,merge_filenames,[("padding2","in2")])
                            ])
                merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
                flow.connect([
                            (merge_filenames,merge,[("out","in_files")]),
                            (merge,outputnode,[("merged_file","diffusion_preproc")])
                            ])
            else:
                flow.connect([
                            (eddy_correct,outputnode,[("eddy_corrected","diffusion_preproc")])
                            ])
        else:
            flow.connect([
                (mr_convert_b,outputnode,[("converted","diffusion_preproc")]),
                (inputnode,outputnode,[("bvecs","bvecs_rot")])
                ])
        # #mr_convertB.inputs.grad_fsl = ('bvecs', 'bvals')
        # flow.connect([
        #             (mr_convertF,mr_convertB,[("converted","in_file")])
        #             ])

        # if self.config.motion_correction:
        #     mc_flirt = pe.Node(interface=fsl.MCFLIRT(out_file='motion_corrected.nii.gz',ref_vol=0),name='motion_correction')
        #     flow.connect([
        #                 (mr_convert_b,mc_flirt,[("converted","in_file")])
        #                 ])
        #     if self.config.eddy_current_correction:
        #         eddy_correct = pe.Node(interface=fsl.EddyCorrect(ref_num=0,out_file='eddy_corrected.nii.gz'),name='eddy_correct')
        #         flow.connect([
        #                     (mc_flirt,eddy_correct,[("out_file","in_file")])
        #                     ])
        #         if self.config.start_vol > 0 and self.config.end_vol == self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
        #             flow.connect([
        #                         (split_vol,merge_filenames,[("padding1","in1")]),
        #                         (eddy_correct,merge_filenames,[("eddy_corrected","in2")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         elif self.config.start_vol > 0 and self.config.end_vol < self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(3),name='merge_files')
        #             flow.connect([
        #                         (split_vol,merge_filenames,[("padding1","in1")]),
        #                         (eddy_correct,merge_filenames,[("eddy_corrected","in2")]),
        #                         (split_vol,merge_filenames,[("padding2","in3")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         elif self.config.start_vol == 0 and self.config.end_vol < self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
        #             flow.connect([
        #                         (eddy_correct,merge_filenames,[("eddy_corrected","in1")]),
        #                         (split_vol,merge_filenames,[("padding2","in2")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         else:
        #             flow.connect([
        #                         (eddy_correct,outputnode,[("eddy_corrected","diffusion_preproc")])
        #                         ])
        #     else:
        #         if self.config.start_vol > 0 and self.config.end_vol == self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
        #             flow.connect([
        #                         (split_vol,merge_filenames,[("padding1","in1")]),
        #                         (mc_flirt,merge_filenames,[("out_file","in2")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         elif self.config.start_vol > 0 and self.config.end_vol < self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(3),name='merge_files')
        #             flow.connect([
        #                         (split_vol,merge_filenames,[("padding1","in1")]),
        #                         (mc_flirt,merge_filenames,[("out_file","in2")]),
        #                         (split_vol,merge_filenames,[("padding2","in3")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         elif self.config.start_vol == 0 and self.config.end_vol < self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
        #             flow.connect([
        #                         (mc_flirt,merge_filenames,[("out_file","in1")]),
        #                         (split_vol,merge_filenames,[("padding2","in2")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         else:
        #             flow.connect([
        #                         (mc_flirt,outputnode,[("out_file","diffusion_preproc")])
        #                         ])
        # else:
        #     if self.config.eddy_current_correction:
        #         eddy_correct = pe.Node(interface=fsl.EddyCorrect(ref_num=0,out_file="eddy_corrected.nii.gz"),name='eddy_correct')
        #         flow.connect([
        #                     (processing_input,eddy_correct,[("diffusion","in_file")])
        #                     ])
        #         if self.config.start_vol > 0 and self.config.end_vol == self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
        #             flow.connect([
        #                         (split_vol,merge_filenames,[("padding1","in1")]),
        #                         (eddy_correct,merge_filenames,[("eddy_corrected","in1")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         elif self.config.start_vol > 0 and self.config.end_vol < self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(3),name='merge_files')
        #             flow.connect([
        #                         (split_vol,merge_filenames,[("padding1","in1")]),
        #                         (eddy_correct,merge_filenames,[("eddy_corrected","in1")]),
        #                         (split_vol,merge_filenames,[("padding2","in3")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         elif self.config.start_vol == 0 and self.config.end_vol < self.config.max_vol:
        #             merge_filenames = pe.Node(interface=util.Merge(2),name='merge_files')
        #             flow.connect([
        #                         (eddy_correct,merge_filenames,[("eddy_corrected","in1")]),
        #                         (split_vol,merge_filenames,[("padding2","in2")]),
        #                         ])
        #             merge = pe.Node(interface=fsl.Merge(dimension='t'),name="merge")
        #             flow.connect([
        #                         (merge_filenames,merge,[("out","in_files")]),
        #                         (merge,outputnode,[("merged_file","diffusion_preproc")])
        #                         ])
        #         else:
        #             flow.connect([
        #                         (eddy_correct,outputnode,[("eddy_corrected","diffusion_preproc")])
        #                         ])
        #     else:
        #         flow.connect([
				    # (inputnode,outputnode,[("diffusion","diffusion_preproc")]),
				    # ])
        

    def define_inspect_outputs(self):
        print "stage_dir : %s" % self.stage_dir
        if self.config.denoising:
            denoising_results_path = os.path.join(self.stage_dir,"dwi_denoise","result_dwi_denoise.pklz")
            if(os.path.exists(denoising_results_path)):
                dwi_denoise_results = pickle.load(gzip.open(denoising_results_path))
                print dwi_denoise_results.outputs.out_file
                print dwi_denoise_results.outputs.out_noisemap
                self.inspect_outputs_dict['DWI denoised image'] = ['mrview',dwi_denoise_results.outputs.out_file]
                self.inspect_outputs_dict['Noise map'] = ['mrview',dwi_denoise_results.outputs.out_noisemap]

        if self.config.bias_field_correction:
            bias_field_correction_results_path = os.path.join(self.stage_dir,"dwi_biascorrect","result_dwi_biascorrect.pklz")
            if(os.path.exists(bias_field_correction_results_path)):
                dwi_biascorrect_results = pickle.load(gzip.open(bias_field_correction_results_path))
                print dwi_biascorrect_results.outputs.out_file
                print dwi_biascorrect_results.outputs.out_bias
                self.inspect_outputs_dict['Bias field corrected image'] = ['mrview',dwi_biascorrect_results.outputs.out_file]
                self.inspect_outputs_dict['Bias field'] = ['mrview',dwi_biascorrect_results.outputs.out_bias]

        if self.config.eddy_current_and_motion_correction:
            eddy_results_path = os.path.join(self.stage_dir,"eddy","result_eddy.pklz")
            if(os.path.exists(eddy_results_path)):
                eddy_results = pickle.load(gzip.open(eddy_results_path))
                self.inspect_outputs_dict['Eddy current corrected image'] = ['mrview',eddy_results.outputs.eddy_corrected]
        
        self.inspect_outputs = self.inspect_outputs_dict.keys()           

            
    def has_run(self):
        if not self.config.eddy_current_and_motion_correction:
            if not self.config.denoising and not self.config.bias_field_correction:
                return True
            else:
                return os.path.exists(os.path.join(self.stage_dir,"mr_convert_b","result_mr_convert_b.pklz"))
        else:
            return os.path.exists(os.path.join(self.stage_dir,"eddy","result_eddy.pklz"))
