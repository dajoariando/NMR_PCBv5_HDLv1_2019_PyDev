'''
Created on Mar 30, 2018

@author: David Ariando

in progress:
*** direct_read, a setting to read data directly from SDRAM using Python is implemented using the same CPMG_iterate C-function (with the loop handled by Python instead of C).
It is a slower operation than using C to write to SDCard directly. It might be due to every iteration will
generate acqu.par separately in separate folder. Or MAYBE [less likely] writing to SDRAM via DMA is slower than writing directly
to a text file. Or MAYBE because every iteration runs CPMG_iterate with 1-iteration, the C program is called
number_of_iteration times. Also the computation of SNR/echo/scan is wrong in compute_iterate due to having
only 1 as a number_of_iteration in acqu.par. It seems to be no point of using Python if C still needs to be called.
So many problems yet not having better speed. It might be better to write everything in Python instead.
'''

#!/usr/bin/python

import os
import time
from nmr_std_function.data_parser import parse_simple_info
from nmr_std_function.nmr_functions import compute_iterate
from nmr_std_function.nmr_functions import calcP90
from nmr_std_function.nmr_class import tunable_nmr_system_2018
from nmr_std_function.data_parser import parse_csv_float2col
import matplotlib.pyplot as plt
from scipy import signal
import pydevd


# settings
data_folder = "/root/NMR_DATA"  # the nmr data folder
en_fig = 1  # enable figure
en_remote_dbg = 0  # enable remote debugging. Enable debug server first!
direct_read = 0   # perform direct read from SDRAM. use with caution above!
meas_time = 1  # measure time
process_data = 0  # process data within the SoC

# cpmg settings
cpmg_freq = 4.062  # 4.06625 for CWRU lab
pulse1_us = 2.5  # 75 for Cheng's coil. pulse pi/2 length.
pulse2_us = 1.6 * pulse1_us  # pulse pi length
pulse1_dtcl = 0.5  # useless with current code
pulse2_dtcl = 0.5  # useless with current code
echo_spacing_us = 1000  # cheng' coil : 750
scan_spacing_us = 50000
samples_per_echo = 128  # number of points
echoes_per_scan = 128  # number of echos
# put to 10 for broadband board and 6 for tunable board
init_adc_delay_compensation = 6  # acquisition shift microseconds.
number_of_iteration = 2  # number of averaging
ph_cycl_en = 1
pulse180_t1_int = 0
delay180_t1_int = 0

# coil param and measured voltage across the coil
Vpp = 215 + 219  # 190
rs = 1.2
L = 2.438e-6
coilLength = 36e-3
numTurns = 37
coilFactor = 0.675  # measured_eff_p90/calc'ed_p90. Equal to 1 for calc'ed_p90
# magnet param
B0 = 0.0997  # T
gamma = 42.57  # MHz/T
print("freq estimate: %3.3f MHz" % (gamma * B0))
P90, Pwatt = calcP90(Vpp, rs, L, cpmg_freq * 1e6,
                     numTurns, coilLength, coilFactor)
print("P90 len estimate: %3.3f us, power estimate: %3.3f Watts" %
      (P90 * 1e6, Pwatt))

if (meas_time):
    start_time = time.time()

# instantiate nmr object
nmrObj = tunable_nmr_system_2018(data_folder, en_remote_dbg)

# system setup
nmrObj.initNmrSystem()  # necessary to set the GPIO initial setting
# nmrObj.turnOnPower()
nmrObj.assertControlSignal(nmrObj.PSU_15V_TX_P_EN_msk | nmrObj.PSU_15V_TX_N_EN_msk | nmrObj.PSU_5V_TX_N_EN_msk |
                           nmrObj.PSU_5V_ADC_EN_msk | nmrObj.PSU_5V_ANA_P_EN_msk |
                           nmrObj.PSU_5V_ANA_N_EN_msk)

# nmrObj.setPreampTuning(-2.93, 3.7)  # for 2.43MHz BLACK
# nmrObj.setPreampTuning(-3.1, -4.2)  # for 1.87MHz BLACK
# nmrObj.setMatchingNetwork(2700, 350)  # for 2.43MHz BLACK
# nmrObj.setMatchingNetwork(3180, 420)  # for 1.87MHz BLACK
# nmrObj.setMatchingNetwork(255, 76)  # 4.05 MHz
# nmrObj.setMatchingNetwork(189, 74)  # 4.17 MHz KeA
nmrObj.setPreampTuning(-2.5, 3.7)
nmrObj.setMatchingNetwork(210, 100)  # 4.17 MHz AFE
# nmrObj.setSignalPath()
# for normal path
# nmrObj.assertControlSignal(nmrObj.AMP_HP_LT1210_EN_msk | nmrObj.PAMP_IN_SEL_RX_msk | nmrObj.RX_IN_SEL_1_msk)
# for reflection path or broadband board
if (nmrObj.PCBVer == 'v4.0_and_below'):
    nmrObj.assertControlSignal(nmrObj.AMP_HP_LT1210_EN_msk |
                               nmrObj.PAMP_IN_SEL_RX_msk | nmrObj.RX_IN_SEL_1_msk)
elif (nmrObj.PCBVer == 'v5.0'):
    nmrObj.assertControlSignal(
        nmrObj.RX1_1H_msk | nmrObj.RX1_1L_msk | nmrObj.RX2_L_msk | nmrObj.RX2_H_msk | nmrObj.RX_SEL1_msk | nmrObj.RX_FL_msk | nmrObj.PAMP_IN_SEL2_msk)

if (direct_read):
    datain = nmrObj.cpmgSequenceDirectRead(cpmg_freq, pulse1_us, pulse2_us, pulse1_dtcl, pulse2_dtcl, echo_spacing_us, scan_spacing_us, samples_per_echo,
                                           echoes_per_scan, init_adc_delay_compensation, number_of_iteration, ph_cycl_en,
                                           pulse180_t1_int, delay180_t1_int)
else:
    nmrObj.cpmgSequence(cpmg_freq, pulse1_us, pulse2_us, pulse1_dtcl, pulse2_dtcl, echo_spacing_us, scan_spacing_us, samples_per_echo,
                        echoes_per_scan, init_adc_delay_compensation, number_of_iteration,
                        ph_cycl_en, pulse180_t1_int, delay180_t1_int)
    datain = []  # set datain to 0 because the data will be read from file instead

# turn off system
# nmrObj.turnOffSystem()
# for normal path
# nmrObj.deassertControlSignal(
#    nmrObj.AMP_HP_LT1210_EN_msk | nmrObj.PAMP_IN_SEL_RX_msk | nmrObj.RX_IN_SEL_1_msk)
# for reflection path or broadband board
if (nmrObj.PCBVer == 'v4.0_and_below'):
    nmrObj.deassertControlSignal(nmrObj.AMP_HP_LT1210_EN_msk |
                                 nmrObj.PAMP_IN_SEL_RX_msk | nmrObj.RX_IN_SEL_2_msk)
elif (nmrObj.PCBVer == 'v5.0'):
    nmrObj.assertControlSignal(
        nmrObj.RX1_1H_msk | nmrObj.RX1_1L_msk | nmrObj.RX2_L_msk | nmrObj.RX2_H_msk | nmrObj.RX_SEL1_msk | nmrObj.RX_FL_msk | nmrObj.PAMP_IN_SEL2_msk)

nmrObj.setMatchingNetwork(0, 0)
nmrObj.setPreampTuning(0, 0)
nmrObj.deassertControlSignal(nmrObj.PSU_15V_TX_P_EN_msk | nmrObj.PSU_15V_TX_N_EN_msk | nmrObj.PSU_5V_TX_N_EN_msk |
                             nmrObj.PSU_5V_ADC_EN_msk | nmrObj.PSU_5V_ANA_P_EN_msk | nmrObj.PSU_5V_ANA_N_EN_msk)

if (process_data):
    meas_folder = parse_simple_info(data_folder, 'current_folder.txt')
    (a, a_integ, a0, snr, T2, noise, res, theta, data_filt, echo_avg, Df, t_echospace) = compute_iterate(
        data_folder, meas_folder[0], 0, 0, 0, direct_read, datain, en_fig)

if (meas_time):
    elapsed_time = time.time() - start_time
    print("time elapsed: %.3f" % (elapsed_time))
