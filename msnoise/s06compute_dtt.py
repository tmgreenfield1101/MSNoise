"""
This code is responsible for the calculation of dt/t using the result of the
MWCS calculations.


Configuration Parameters
~~~~~~~~~~~~~~~~~~~~~~~~

* |dtt_lag|
* |dtt_v|
* |dtt_minlag|
* |dtt_width|
* |dtt_sides|
* |dtt_mincoh|
* |dtt_maxerr|
* |dtt_maxdt|

The dt/t is determined as the slope of the delays vs time lags. The slope is
calculated a weighted linear regression (WLS) through selected points.

1. The selection of points is first based on the time lag criteria.
The minimum time lag can either be defined absolutely or dynamically.
When ``dtt_lag`` is set to "dynamic" in the database, the inter-station distance
is used to determine the minimum time lag. This lag is calculated from the
distance and a velocity configured (``dtt_v``). The velocity is determined by
the user so that the minlag doesn't include the ballistic waves. For example,
if ballistic waves are visible with a velocity of 2 km/s, one could configure
dtt_v=1.0.
This way, if stations are located 15 km apart, the minimum lag time will be
set to 15 s. The ``dtt_width`` determines the width of the lag window used. A
value of 30.0 means the process will use time lags between 15 and 45 s in the
example above, on both sides if configured (``dtt_sides``), or only causal or
acausal parts of the CCF. The following figure shows the static time lags of
``dtt_width`` = 40s starting at ``dtt_minlag`` = 10s and the dynamic time lags
for a ``dtt_v`` = 1.0 km/s for the Piton de La Fournaise network (including
stations *not* on the volcano),

.. note:: It seems obvious that these parameters are frequency-dependent, but
    they are currently common for all filters !

.. image:: ../.static/static.png

.. image:: ../.static/dynamic.png

.. warning:: In order to use the dynamic time lags, one has to provide the
   station coordinates !


2. Using example values above, we chose to use only 15-45 s coda part of the
signal, neglecting direct waves in the 0-15 seconds range. We then select data
which match three other thresholds: ``dtt_mincoh``, ``dtt_maxerr`` and
``dtt_maxdt``.

.. image:: ../.static/Figure04_dttmatrix_01_005DAYS_ZZ-2010-10-12_cmyk.png

Each of the 4 left subplot of this figure shows a colormapper matrix of which
each row
corresponds to the data of 1 station pair and each column corresponds to
different time lags. The cells are then colored using, from left to right:
Delays, Errors, Phase Coherence and Data Selection. 

Once data (cells) have been selected, they are analyzed two times: first using
a WLS that is forced to pass the origin (0,0) and second when a constant is
added to allow for the WLS to be offset from the origin. For each value, the
error is computed and stored. M0 and EM0 are the slope and its error for the
first WLS, and M, EM together with A and EA are the slope, its error, the
constant and its error for the second WLS. The output of this calculation
is a table, with one row for each station pair.


.. code-block:: python

    Date,          A,        EA,        EM,       EM0,         M,          M0,       Pairs
    2013-01-06,-0.1683728,0.0526606,0.00208377,0.00096521, 0.00682021, 0.00037757,BE_GES_BE_HOU
    2013-01-06,-0.0080464,0.0577936,0.00291327,0.00097298,-0.00226910,-0.00264354,BE_GES_BE_MEM
    2013-01-06, 0.1007472,0.0144648,0.00179566,0.00454172,-0.00145738, 0.00741478,BE_GES_BE_RCHB
    2013-01-06,-0.0556811,0.0098926,0.00057839,0.00108102,-0.00328965,-0.00136075,BE_GES_BE_SKQ
    2013-01-06, 0.0150866,0.0202243,0.00096543,0.00089832, 0.00083714, 0.00104507,BE_GES_BE_STI
    2013-01-06, 0.0268309,0.0328997,0.00153137,0.00150261, 0.00302331, 0.00302451,BE_GES_BE_UCC
    2013-01-06,-0.0121293,0.0043351,0.00039019,0.00041347, 0.00025836,-0.00042709,BE_HOU_BE_MEM
    2013-01-06, 0.1076247,0.0188662,0.00076824,0.00216383,-0.00030791, 0.00112692,BE_HOU_BE_RCHB
    2013-01-06,-0.0468485,0.0194492,0.00069968,0.00078207,-0.00066133, 0.00027102,BE_HOU_BE_SKQ
    2013-01-06, 0.0203057,0.0161316,0.00131522,0.00131182, 0.00051626,-3.10306611,BE_HOU_BE_STI
    ...
    2013-01-06,-0.0022588,0.0037141,0.00010340,9.1996e-05, 0.00073635, 0.00076238,ALL


To run this script:

.. code-block:: bash

    msnoise cc dvv compute_dtt


Grouping Station Pairs
~~~~~~~~~~~~~~~~~~~~~~~
Although not clearly visible on the figure above, the very last row of the
matrix doesn't contain information about one station pair, but contains
a weighted mean of all delays (from all pairs) for each time lag. For each time
lag, delays from each pair is taken into account if it satisfies the same
criteria as for the individual data selection. Once the last row (the ALL line)
has been calculated, it goes through the normal process of the double WLS and
is saved to the output file, as visible above. In the future, MSNoise will be
able to treat as many groups as the user want, allowing, e.g. a "crater" and
a "slopes" groups.

Forcing vs No Forcing through Origin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The reason for allowing the WLS to cross the axis elsewhere than on (0,0) is,
for example, to study the potential clock drifts or noise source position
variations. By default, the ``msnoise plot dvv`` plot shows the results
of the ```Not Forced`` WLS.

Mean of All Pairs vs Mean Pair
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning:: the ``ALL`` pair is still calculated and output in the DTT files,
    but its output is no longer displayed on the graphs. *new in 1.6*.

The dt/t calculated using the mean pair (ALL, in red on subplots 4 and 5)
and by calculating the weighted mean of the dt/t of all pairs (in green)
don't show a significant difference. The standard deviation around the latter
is more spread than on the former, but this has to be investigated.


"""

from obspy.signal.regression import linear_regression
from .api import *


import logbook


def wavg_wstd(data, errors):
    d = data
    errors[errors == 0] = 1e-6
    w = 1. / errors
    wavg = (d * w).sum() / w.sum()
    N = len(np.nonzero(w)[0])
    wstd = np.sqrt(np.sum(w * (d - wavg) ** 2) / ((N - 1) * np.sum(w) / N))
    return wavg, wstd


def main(interval=1, loglevel="INFO"):
    logger = logbook.Logger(__name__)
    # Reconfigure logger to show the pid number in log records
    logger = get_logger('msnoise.compute_dtt_child', loglevel,
                        with_pid=True)
    logger.info('*** Starting: Compute DT/T ***')
    db = connect()
    params = get_params(db)

    start, end, datelist = build_movstack_datelist(db)

    mov_stacks = params.mov_stack

    components_to_compute = get_components_to_compute(db)
    updated_dtt = updated_days_for_dates(
        db, start, end, '%', jobtype='DTT', returndays=True,
        interval=datetime.timedelta(days=interval))
    interstations = {}
    for sta1, sta2 in get_station_pairs(db):
        s1 = "%s_%s" % (sta1.net, sta1.sta)
        s2 = "%s_%s" % (sta2.net, sta2.sta)
        if s1 == s2:
            interstations["%s_%s" % (s1, s2)] = 0.0
        else:
            interstations["%s_%s"%(s1,s2)] = get_interstation_distance(sta1,
                                                                       sta2,
                                                                       sta1.coordinates)
        
    filters = get_filters(db, all=False)
    while is_next_job(db, jobtype='DTT'):
        jobs = get_next_job(db, jobtype='DTT')

        stations = []
        pairs = []
        refs = []
        for f in filters:
            filterid = int(f.ref)
            for components in params.all_components:
                for mov_stack in mov_stacks:
                    logger.info('Loading mov=%i days for filter=%02i' %
                                 (mov_stack, filterid))
                    first = True
                    for job in jobs:
                        refs.append(job.ref)
                        pairs.append(job.pair)
                        netsta1, netsta2 = job.pair.split(':')
                        stations.append(netsta1)
                        stations.append(netsta2)
                        current = job.day
                        sta1 = netsta1
                        sta2 = netsta2
                        pair = "%s_%s" % (netsta1, netsta2)
                        df = get_mwcs(db, netsta1, netsta2, filterid, components, current, mov_stack)
                        if not len(df):
                            continue
                        # dist = get_interstation_distance(station1, station2,
                        #                                  station1.coordinates)
                        n1, s1, l1 = sta1.split(".")
                        n2, s2, l2 = sta2.split(".")
                        dpair = "%s_%s_%s_%s" % (n1, s1, n2, s2)
                        dist = interstations[dpair] if dpair in interstations else 0.0
                        if dist == 0. and params.dtt_lag == "dynamic":
                            logger.debug('%s: Distance is Zero?!' % pair)
                        tArray = df.index.values
                        if params.dtt_lag == "static":
                            lmlag = -params.dtt_minlag
                            rmlag = params.dtt_minlag
                        else:
                            lmlag = -dist / params.dtt_v
                            rmlag = dist / params.dtt_v
                        lMlag = lmlag - params.dtt_width
                        rMlag = rmlag + params.dtt_width

                        if params.dtt_sides == "both":
                            tindex = np.where(((tArray >= lMlag) & (tArray <= lmlag)) | ((tArray >= rmlag) & (tArray <= rMlag)))[0]
                        elif params.dtt_sides == "left":
                            tindex = np.where((tArray >= lMlag) & (tArray <= lmlag))[0]
                        else:
                            tindex = np.where((tArray >= rmlag) & (tArray <= rMlag))[0]

                        tmp = np.setdiff1d(np.arange(len(tArray)),tindex)
                        df.iloc[tmp, df.columns.get_indexer(['err', ])] = 1.0
                        df.iloc[tmp, df.columns.get_indexer(['coh', ])] = 0.0

                        if first:
                            tArray = df.index.values
                            dtArray = df['dt']
                            errArray = df['err']
                            cohArray = df['coh']
                            pairArray = [pair, ]
                            first = False
                        else:
                            dtArray = np.vstack((dtArray, df['dt']))
                            errArray = np.vstack((errArray, df['err']))
                            cohArray = np.vstack((cohArray, df['coh']))
                            pairArray.append(pair)
                        del df

    
                    if not first:
                        #~ tindex = np.tindwhere(((tArray >= lMlag) & (tArray <= lmlag)) | (
                            #~ (tArray >= rmlag) & (tArray <= rMlag)))[0]
    
                        Dates = []
                        Pairs = []
                        M = []
                        EM = []
                        A = []
                        EA = []
                        M0 = []
                        EM0 = []
                        if len(pairArray) != 1:
                            # first stack all pairs to a ALL mean pair, using
                            # indexes of selected values:
                            new_dtArray = np.zeros(len(tArray))
                            new_errArray = np.zeros(len(tArray)) + 9999
                            new_cohArray = np.zeros(len(tArray))
                            for i in range(len(tArray)):
                                #~ if i in tindex:
                                if 1:
                                    cohindex = np.where(
                                        cohArray[:, i] >= params.dtt_mincoh)[0]
                                    errindex = np.where(
                                        errArray[:, i] <= params.dtt_maxerr)[0]
                                    dtindex = np.where(
                                        np.abs(dtArray[:, i]) <= params.dtt_maxdt)[0]
    
                                    index = np.intersect1d(cohindex, errindex)
                                    index = np.intersect1d(index, dtindex)
    
                                    wavg, wstd = wavg_wstd(
                                        dtArray[:, i][index],
                                        errArray[:, i][index])
                                    new_dtArray[i] = wavg
                                    new_errArray[i] = wstd
                                    new_cohArray[i] = 1.0
    
                            dtArray = np.vstack((dtArray, new_dtArray))
                            errArray = np.vstack((errArray, new_errArray))
                            cohArray = np.vstack((cohArray, new_cohArray))
                            pairArray.append("ALL")
                            del new_cohArray, new_dtArray, new_errArray,\
                                cohindex, errindex, dtindex, wavg, wstd
                            
                            # then stack selected pais to GROUPS:
                            groups = {}
                            npairs = len(pairArray)-1
                            for group in groups.keys():
                                new_dtArray = np.zeros(len(tArray))
                                new_errArray = np.zeros(len(tArray)) + 9999
                                new_cohArray = np.zeros(len(tArray))
                                pairindex = []
                                for j, pair in enumerate(pairArray[:npairs]):
                                    net1, sta1, net2, sta2 = pair.split('_')
                                    if sta1 in groups[group] and \
                                                    sta2 in groups[group]:
                                        pairindex.append(j)
                                pairindex = np.array(pairindex)

                                for i in range(len(tArray)):
                                    #~ if i in tindex:
                                    if 1:
                                        cohindex = np.where(
                                            cohArray[:, i] >= params.dtt_mincoh)[0]
                                        errindex = np.where(
                                            errArray[:, i] <= params.dtt_maxerr)[0]
                                        dtindex = np.where(
                                            np.abs(dtArray[:, i]) <= params.dtt_maxdt)[0]
        
                                        index = np.intersect1d(cohindex,
                                                               errindex)
                                        index = np.intersect1d(index, dtindex)
                                        index = np.intersect1d(index, pairindex)
                                        
        
                                        wavg, wstd = wavg_wstd(
                                            dtArray[:, i][index],
                                            errArray[:, i][index])
                                        new_dtArray[i] = wavg
                                        new_errArray[i] = wstd
                                        new_cohArray[i] = 1.0
        
                                dtArray = np.vstack((dtArray, new_dtArray))
                                errArray = np.vstack((errArray, new_errArray))
                                cohArray = np.vstack((cohArray, new_cohArray))
                                pairArray.append(group)
                                del new_cohArray, new_dtArray, new_errArray,\
                                    cohindex, errindex, dtindex, wavg, wstd
                                # END OF GROUP HANDLING
    
                        # then process all pairs + the ALL
                        if len(dtArray.shape) == 1:  # if there is only one pair:
                            dtArray = dtArray.values.reshape((1, dtArray.shape[0]))
                            cohArray = cohArray.values.reshape((1, cohArray.shape[0]))
                            errArray = errArray.values.reshape((1, errArray.shape[0]))
    
                        used = np.zeros(dtArray.shape)
    
                        for i, pair in enumerate(pairArray):
                            cohindex = np.where(cohArray[i] >= params.dtt_mincoh)[0]
                            errindex = np.where(errArray[i] <= params.dtt_maxerr)[0]
                            dtindex = np.where(np.abs(dtArray[i]) <= params.dtt_maxdt)[0]
    
                            #~ index = np.intersect1d(tindex, cohindex)
                            index = np.intersect1d(cohindex, errindex)
                            index = np.intersect1d(index, dtindex)
    
                            used[i][index] = 1.0

                            w = 1.0 / errArray[i][index]
                            w[~np.isfinite(w)] = 1.0
                            VecXfilt = tArray[index]
                            VecYfilt = dtArray[i][index]
                            if len(VecYfilt) >= 2:
                                m, a, em, ea = linear_regression(
                                    VecXfilt, VecYfilt, w,
                                    intercept_origin=False)
                                m0, em0 = linear_regression(
                                    VecXfilt, VecYfilt, w,
                                    intercept_origin=True)
                                M.append(m)
                                EM.append(em)
                                A.append(a)
                                EA.append(ea)

                                M0.append(m0)
                                EM0.append(em0)

                                Dates.append(current)
                                Pairs.append(pair)

                                del m, a, em, ea, m0, em0

                            del VecXfilt, VecYfilt, w
                            del index, cohindex, errindex, dtindex
    
                        logger.debug(
                            "%s: exporting: %i pairs" % (current,
                                                         len(pairArray)))
                        df = pd.DataFrame(
                            {'Pairs': Pairs, 'M': M, 'EM': EM, 'A': A, 'EA': EA,
                             'M0': M0, 'EM0': EM0},
                            index=Dates)
                        # TODO Needs to be changed to save via the API
                        output = os.path.join(
                            'DTT', "%02i" % filterid, "%03i_DAYS" % mov_stack,
                            components)
                        if not os.path.isdir(output):
                            os.makedirs(output)
                        fn = os.path.join(output, '%s.txt' % current)
                        if os.path.isfile(fn):
                            existing = pd.read_csv(fn, index_col="Pairs", parse_dates=True)
                            for id, row in df.iterrows():
                                if row.Pairs in existing.index.values:
                                    existing.drop(row.Pairs, inplace=True)
                                    logger.debug("Pair: %s is already in the output file, overwriting" % row.Pairs)
                            existing["Pairs"] = existing.index.values
                            existing.set_index("Date", inplace=True)
                            df = pd.concat([df, existing])
                        df.to_csv(fn, index_label='Date')
                        del df, M, EM, A, EA, M0, EM0, Pairs, Dates, used
                        del tArray, dtArray, errArray, cohArray, pairArray
                        del output
        # THIS SHOULD BE IN THE API
        massive_update_job(db, jobs, "D")

    logger.info('*** Finished: Compute DT/T ***')


if __name__ == "__main__":
    main()
