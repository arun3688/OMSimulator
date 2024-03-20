-- status: correct
-- teardown_command: rm -rf setunits_02_lua/
-- linux: yes
-- ucrt64: yes
-- win: yes
-- mac: no

oms_setCommandLineOption("--suppressPath=true")
oms_setTempDirectory("./setunits_02_lua/")

oms_newModel("model")

oms_addSystem("model.root", oms_system_wc)

oms_addSubModel("model.root.sine", "../resources/Modelica.Blocks.Sources.Sine.fmu")

oms_setReal("model.root.sine.phase", 27)
oms_setReal("model.root.sine.amplitude", -100)
oms_setReal("model.root.sine.freqHz", -300)

oms_setResultFile("model", "")

src, status = oms_exportSnapshot("model")
print(src)

-- change the unit to meter
oms_setUnit("model.root.sine.phase", "m")
oms_setUnit("model.root.sine.amplitude", "m")

src, status = oms_exportSnapshot("model")
print(src)

oms_terminate("model")
oms_delete("model")



-- Result:
-- <?xml version="1.0"?>
-- <oms:snapshot
--   xmlns:oms="https://raw.githubusercontent.com/OpenModelica/OMSimulator/master/schema/oms.xsd"
--   partial="false">
--   <oms:file
--     name="SystemStructure.ssd">
--     <ssd:SystemStructureDescription
--       xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon"
--       xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
--       xmlns:ssv="http://ssp-standard.org/SSP1/SystemStructureParameterValues"
--       xmlns:ssm="http://ssp-standard.org/SSP1/SystemStructureParameterMapping"
--       xmlns:ssb="http://ssp-standard.org/SSP1/SystemStructureSignalDictionary"
--       xmlns:oms="https://raw.githubusercontent.com/OpenModelica/OMSimulator/master/schema/oms.xsd"
--       name="model"
--       version="1.0">
--       <ssd:System
--         name="root">
--         <ssd:Elements>
--           <ssd:Component
--             name="sine"
--             type="application/x-fmu-sharedlibrary"
--             source="resources/0001_sine.fmu">
--             <ssd:Connectors>
--               <ssd:Connector
--                 name="y"
--                 kind="output">
--                 <ssc:Real />
--                 <ssd:ConnectorGeometry
--                   x="1.000000"
--                   y="0.500000" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="amplitude"
--                 kind="parameter">
--                 <ssc:Real />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="freqHz"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="Hz" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="offset"
--                 kind="parameter">
--                 <ssc:Real />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="phase"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="rad" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="startTime"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="s" />
--               </ssd:Connector>
--             </ssd:Connectors>
--             <ssd:ParameterBindings>
--               <ssd:ParameterBinding>
--                 <ssd:ParameterValues>
--                   <ssv:ParameterSet
--                     version="1.0"
--                     name="parameters">
--                     <ssv:Parameters>
--                       <ssv:Parameter
--                         name="phase">
--                         <ssv:Real
--                           value="27"
--                           unit="rad" />
--                       </ssv:Parameter>
--                       <ssv:Parameter
--                         name="freqHz">
--                         <ssv:Real
--                           value="-300"
--                           unit="Hz" />
--                       </ssv:Parameter>
--                       <ssv:Parameter
--                         name="amplitude">
--                         <ssv:Real
--                           value="-100" />
--                       </ssv:Parameter>
--                     </ssv:Parameters>
--                   </ssv:ParameterSet>
--                 </ssd:ParameterValues>
--               </ssd:ParameterBinding>
--             </ssd:ParameterBindings>
--           </ssd:Component>
--         </ssd:Elements>
--         <ssd:Annotations>
--           <ssc:Annotation
--             type="org.openmodelica">
--             <oms:Annotations>
--               <oms:SimulationInformation>
--                 <oms:FixedStepMaster
--                   description="oms-ma"
--                   stepSize="0.001000"
--                   absoluteTolerance="0.000100"
--                   relativeTolerance="0.000100" />
--               </oms:SimulationInformation>
--             </oms:Annotations>
--           </ssc:Annotation>
--         </ssd:Annotations>
--       </ssd:System>
--       <ssd:Units>
--         <ssc:Unit
--           name="Hz">
--           <ssc:BaseUnit
--             s="-1" />
--         </ssc:Unit>
--         <ssc:Unit
--           name="rad">
--           <ssc:BaseUnit />
--         </ssc:Unit>
--         <ssc:Unit
--           name="s">
--           <ssc:BaseUnit
--             s="1" />
--         </ssc:Unit>
--       </ssd:Units>
--       <ssd:DefaultExperiment
--         startTime="0.000000"
--         stopTime="1.000000">
--         <ssd:Annotations>
--           <ssc:Annotation
--             type="org.openmodelica">
--             <oms:Annotations>
--               <oms:SimulationInformation
--                 resultFile=""
--                 loggingInterval="0.000000"
--                 bufferSize="1"
--                 signalFilter="resources/signalFilter.xml" />
--             </oms:Annotations>
--           </ssc:Annotation>
--         </ssd:Annotations>
--       </ssd:DefaultExperiment>
--     </ssd:SystemStructureDescription>
--   </oms:file>
--   <oms:file
--     name="resources/signalFilter.xml">
--     <oms:SignalFilter
--       version="1.0">
--       <oms:Variable
--         name="model.root.sine.y"
--         type="Real"
--         kind="output" />
--       <oms:Variable
--         name="model.root.sine.amplitude"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.freqHz"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.offset"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.phase"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.startTime"
--         type="Real"
--         kind="parameter" />
--     </oms:SignalFilter>
--   </oms:file>
-- </oms:snapshot>
--
-- <?xml version="1.0"?>
-- <oms:snapshot
--   xmlns:oms="https://raw.githubusercontent.com/OpenModelica/OMSimulator/master/schema/oms.xsd"
--   partial="false">
--   <oms:file
--     name="SystemStructure.ssd">
--     <ssd:SystemStructureDescription
--       xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon"
--       xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
--       xmlns:ssv="http://ssp-standard.org/SSP1/SystemStructureParameterValues"
--       xmlns:ssm="http://ssp-standard.org/SSP1/SystemStructureParameterMapping"
--       xmlns:ssb="http://ssp-standard.org/SSP1/SystemStructureSignalDictionary"
--       xmlns:oms="https://raw.githubusercontent.com/OpenModelica/OMSimulator/master/schema/oms.xsd"
--       name="model"
--       version="1.0">
--       <ssd:System
--         name="root">
--         <ssd:Elements>
--           <ssd:Component
--             name="sine"
--             type="application/x-fmu-sharedlibrary"
--             source="resources/0001_sine.fmu">
--             <ssd:Connectors>
--               <ssd:Connector
--                 name="y"
--                 kind="output">
--                 <ssc:Real />
--                 <ssd:ConnectorGeometry
--                   x="1.000000"
--                   y="0.500000" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="amplitude"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="m" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="freqHz"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="Hz" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="offset"
--                 kind="parameter">
--                 <ssc:Real />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="phase"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="m" />
--               </ssd:Connector>
--               <ssd:Connector
--                 name="startTime"
--                 kind="parameter">
--                 <ssc:Real
--                   unit="s" />
--               </ssd:Connector>
--             </ssd:Connectors>
--             <ssd:ParameterBindings>
--               <ssd:ParameterBinding>
--                 <ssd:ParameterValues>
--                   <ssv:ParameterSet
--                     version="1.0"
--                     name="parameters">
--                     <ssv:Parameters>
--                       <ssv:Parameter
--                         name="phase">
--                         <ssv:Real
--                           value="27"
--                           unit="m" />
--                       </ssv:Parameter>
--                       <ssv:Parameter
--                         name="freqHz">
--                         <ssv:Real
--                           value="-300"
--                           unit="Hz" />
--                       </ssv:Parameter>
--                       <ssv:Parameter
--                         name="amplitude">
--                         <ssv:Real
--                           value="-100"
--                           unit="m" />
--                       </ssv:Parameter>
--                     </ssv:Parameters>
--                   </ssv:ParameterSet>
--                 </ssd:ParameterValues>
--               </ssd:ParameterBinding>
--             </ssd:ParameterBindings>
--           </ssd:Component>
--         </ssd:Elements>
--         <ssd:Annotations>
--           <ssc:Annotation
--             type="org.openmodelica">
--             <oms:Annotations>
--               <oms:SimulationInformation>
--                 <oms:FixedStepMaster
--                   description="oms-ma"
--                   stepSize="0.001000"
--                   absoluteTolerance="0.000100"
--                   relativeTolerance="0.000100" />
--               </oms:SimulationInformation>
--             </oms:Annotations>
--           </ssc:Annotation>
--         </ssd:Annotations>
--       </ssd:System>
--       <ssd:Units>
--         <ssc:Unit
--           name="Hz">
--           <ssc:BaseUnit
--             s="-1" />
--         </ssc:Unit>
--         <ssc:Unit
--           name="m">
--           <ssc:BaseUnit />
--         </ssc:Unit>
--         <ssc:Unit
--           name="s">
--           <ssc:BaseUnit
--             s="1" />
--         </ssc:Unit>
--       </ssd:Units>
--       <ssd:DefaultExperiment
--         startTime="0.000000"
--         stopTime="1.000000">
--         <ssd:Annotations>
--           <ssc:Annotation
--             type="org.openmodelica">
--             <oms:Annotations>
--               <oms:SimulationInformation
--                 resultFile=""
--                 loggingInterval="0.000000"
--                 bufferSize="1"
--                 signalFilter="resources/signalFilter.xml" />
--             </oms:Annotations>
--           </ssc:Annotation>
--         </ssd:Annotations>
--       </ssd:DefaultExperiment>
--     </ssd:SystemStructureDescription>
--   </oms:file>
--   <oms:file
--     name="resources/signalFilter.xml">
--     <oms:SignalFilter
--       version="1.0">
--       <oms:Variable
--         name="model.root.sine.y"
--         type="Real"
--         kind="output" />
--       <oms:Variable
--         name="model.root.sine.amplitude"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.freqHz"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.offset"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.phase"
--         type="Real"
--         kind="parameter" />
--       <oms:Variable
--         name="model.root.sine.startTime"
--         type="Real"
--         kind="parameter" />
--     </oms:SignalFilter>
--   </oms:file>
-- </oms:snapshot>
--
-- endResult
