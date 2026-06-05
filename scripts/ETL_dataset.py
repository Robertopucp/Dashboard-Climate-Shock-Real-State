#%%

import pandas as pd
import numpy as np
import re 
import geopandas as gpd

#%%




# Year when the hurricane hits county

def reso_info(x):
    
    regex_search = re.compile('^([0-9]+)-.*') # withdraw firs 4 digits (year of disaster)
    match = regex_search.search(x)
    
    return match.group(1)


if __name__=="__main__":
        
    # Loading datasets

    zhvi = pd.read_csv(r"data\County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
    fema = pd.read_excel(r"data\fema_2000_2025.xlsx")
    state_code =  pd.read_excel(r"data\state_code.xlsx")
    fema_county = pd.read_csv(r"data\DisasterDeclarationsSummaries.csv")
    fema_county.info()
    fema_county.iloc[:,:10]
    fema_county.fyDeclared.value_counts()

    #%%

    ### I. Cleaning FEMA’s Disaster Declarations record



    # Filter dataset - hurricanes classified as major disasters and taking out other US territories (islands)

    exclude = ['AK','HI','PR','GU','AS','MP','VI','FM','MH','PW']

    fema_county_copy = fema_county[~fema_county.state.isin(exclude)].copy()
    fema_county_copy = (fema_county_copy[
        (fema_county_copy.declarationType=='DR')  #  major disasters 
        & (fema_county_copy.incidentType=="Hurricane") # filter out for hurricanes
        & (fema_county_copy.fyDeclared>=2000)]
    )

    # selecting columns 

    fema_county_filter = fema_county_copy[['disasterNumber',
                                        'state',
                                        'designatedArea',
                                        'fyDeclared',
                                        'incidentBeginDate',
                                        'incidentEndDate',           
                                        'declarationTitle',
                                        'fipsStateCode',
                                        'fipsCountyCode']]

    fema_county_filter['forward_year'] = fema_county_filter['incidentBeginDate'].apply(lambda x: reso_info(x)).astype(int) + 1

    # Hurriccane name in Title format

    fema_county_filter['declarationTitle'] = fema_county_filter['declarationTitle'].str.title()
    fema_county_filter['dhurricane'] = 1

    # Taking out ares with fipsCountyCode equals 0, refering to reservation o pretected areas 

    fema_county_filter = fema_county_filter[fema_county_filter.fipsCountyCode!=0]
    # Counting the number of hurricanes that strike more than once per year in a county

    fema_county_filter['count_dup'] = (
        fema_county_filter.groupby(['state','fipsStateCode',	'fipsCountyCode',	'forward_year']).cumcount() + 1
    )
    fema_county_filter_1 = fema_county_filter[fema_county_filter.count_dup==1] # one hurricane ina county-year
    fema_county_filter_2 = fema_county_filter[fema_county_filter.count_dup==2] # two hurricane ina county-year
    fema_county_filter_3 = fema_county_filter[fema_county_filter.count_dup==3] # three hurricane ina county-year
    # Reshape in wide format for hurricanes name

    fema_county_filter_all = pd.merge(
        fema_county_filter_1,
        fema_county_filter_2[['state','fipsStateCode',	'fipsCountyCode',	'forward_year', 'declarationTitle']],
        how = 'left',
        on = ['state','fipsStateCode',	'fipsCountyCode',	'forward_year'],
        validate = "1:1"
    ).merge(
        fema_county_filter_3[['state','fipsStateCode',	'fipsCountyCode',	'forward_year', 'declarationTitle']],
        how = 'left',
        on = ['state','fipsStateCode',	'fipsCountyCode',	'forward_year'],
        validate = "1:1"
    )
    fema_county_filter_all.rename(
        columns={'declarationTitle_x':'declarationTitle1',
                'declarationTitle_y':'declarationTitle2',
                'declarationTitle':'declarationTitle3'
                },
        inplace=True
    )
    cols = ['declarationTitle1', 'declarationTitle2', 'declarationTitle3']

    # Join hurricane names for years where monre than one hurricane strikes in a  county

    fema_county_filter_all['hurricane_name'] = (
        fema_county_filter_all[cols]
        .apply(
            lambda row: ' ,'.join(
                row.dropna()
                .str.replace("Hurricane","",regex=False)
                .str.strip()
            ), axis =1
        )
    )

    fema_county_filter_all.drop(columns=['declarationTitle1',
                                        'declarationTitle2',
                                        'declarationTitle3',
                                        'count_dup'],
                                inplace=True)
    fema_county_filter_all['date2'] = pd.to_datetime(fema_county_filter_all['incidentEndDate'],
                                        format='mixed')

    fema_county_filter_all['date1'] = fema_county_filter_all['date2'].dt.year.astype('Int64').astype(str) + 'm' + fema_county_filter_all['date2'].dt.month.astype('Int64').astype(str)

    fema_county_filter_all.drop(columns=['incidentEndDate','date2'],
                                inplace=True)

    # Expanding 12 additional months after the hurricane ends

    fema_county_filter_all['month_offset'] = [list(range(12))] * len(fema_county_filter_all)


    # stacking additional months

    df_expanded = fema_county_filter_all.explode('month_offset')

    df_expanded['date1'] = pd.to_datetime(df_expanded['date1'], format='%Ym%m')

    df_expanded['date'] = df_expanded.apply(
        lambda x: x['date1'] + pd.DateOffset(months=x['month_offset']),
        axis=1
    )

    df_expanded['date'] = df_expanded['date'].dt.year.astype(str) + 'm' + df_expanded['date'].dt.month.astype(str)

    df_expanded['date_format'] = pd.to_datetime(
        df_expanded['date'].str.replace('m', '-'),
        format='%Y-%m'
    )

    # droping auxiliar date column 

    del df_expanded['date1'], df_expanded['month_offset']
    df_expanded
    df_expanded.sort_values(['fipsStateCode','fipsCountyCode','hurricane_name','date_format'],
                            inplace=True)

    df_expanded = df_expanded.drop_duplicates(
        subset=['fipsStateCode','fipsCountyCode','date'],
        keep='first'
    )
    df_expanded.sort_values(['fipsStateCode','fipsCountyCode','hurricane_name','date_format'],
                            inplace=True)

    ### II. Cleaning Zillow’s county-level Home Value Index dataset
    # Droppping Alaska and Hawai  

    zhvi_copy = (zhvi[~zhvi.StateName.isin(['AK',
                                        'HI'])]
                .copy()
                .drop(columns=['SizeRank','RegionType','StateName','Metro'])            
    )

    # reshape a long format

    zhvi_long = (zhvi_copy.melt(
        id_vars=['RegionID','RegionName','State','StateCodeFIPS','MunicipalCodeFIPS'],
        var_name='fulldate',
        value_name='zhvi_value'
    )
    .sort_values(['RegionID','fulldate'])
    .reset_index(drop=True)
    )

    # Full date format
    zhvi_long['fulldate'] = pd.to_datetime(zhvi_long['fulldate'])

    # Date in year-month
    zhvi_long['date'] = zhvi_long['fulldate'].dt.year.astype(str) + 'm' + zhvi_long['fulldate'].dt.month.astype(str)

    # Year
    zhvi_long['year'] = zhvi_long['fulldate'].dt.year
    zhvi_long
    # Merge Zillow’s county-level Home Value Index and Zillow’s county-level Home Value Index

    dataset_merge = pd.merge(
        zhvi_long,
        df_expanded,
        how = 'left',
        left_on=['State','StateCodeFIPS','MunicipalCodeFIPS','date'],
        right_on=['state','fipsStateCode',	'fipsCountyCode','date'],
        validate='1:1'
    )
    # Replace nan in dummy hurricane per county and year

    dataset_merge['dhurricane'] = dataset_merge['dhurricane'].fillna(0)

    # Indicator of counties affected by at least one hurricane, spanning 2020-2026

    dataset_merge['indicator'] = dataset_merge.groupby(['StateCodeFIPS','MunicipalCodeFIPS'])['dhurricane'].transform(max)

    dataset_merge = dataset_merge[dataset_merge.indicator==1]
    # State and county in the right format

    dataset_merge['StateCodeFIPS'] = dataset_merge['StateCodeFIPS'].astype(str).str.zfill(2)
    dataset_merge['MunicipalCodeFIPS'] = dataset_merge['MunicipalCodeFIPS'].astype(str).str.zfill(3)

    # Creating Country ID similar to geoJson County USA

    dataset_merge['GEO_ID'] = ("0500000US" +
        dataset_merge['StateCodeFIPS'] +
        dataset_merge['MunicipalCodeFIPS']
    )
    state_map = {
        "TX": "Texas",
        "GA": "Georgia",
        "VA": "Virginia",
        "NC": "North Carolina",
        "MS": "Mississippi",
        "AL": "Alabama",
        "PA": "Pennsylvania",
        "FL": "Florida",
        "LA": "Louisiana",
        "SC": "South Carolina",
        "NY": "New York",
        "WV": "West Virginia",
        "MD": "Maryland",
        "NJ": "New Jersey",
        "AR": "Arkansas",
        "VT": "Vermont",
        "MA": "Massachusetts",
        "NH": "New Hampshire",
        "ME": "Maine",
        "CT": "Connecticut",
        "CA": "California",
        "RI": "Rhode Island",
        "DE": "Delaware",
        "OH": "Ohio",
        "DC": "District of Columbia"
    }


    # Clean State and County names 

    dataset_merge["State"] = dataset_merge["State"].map(state_map)
    dataset_merge['RegionName'] = dataset_merge['RegionName'].str.replace('County', '').str.strip()
    dataset_merge
    dataset_merge.to_csv(r"data\zhvi_hurricane_dataset.csv",
                        index=False)


    # %%
