/*
 * Copyright (c) 2024 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { SceneConfig } from 'arkAnalyzer/src/Config';
import { Scene } from 'arkAnalyzer/src/Scene';
import { ArkFile, ArkMethod, CallGraph, CallGraphBuilder, DEFAULT_ARK_CLASS_NAME, JsonPrinter, MethodSignature, Printer, PrinterBuilder } from 'arkAnalyzer/src';
import { PageTransitionGraph} from '../../src/ptg/model/PageTransitionGraph';
import { PTGModelBuilder} from '../../src/ptg/model/builder/AbstractPTGModelBuilder';
import fs from 'fs';
import path from 'path';

let config: SceneConfig = new SceneConfig()
config.buildFromJson('./tests/ptgTest/PTGTestConfig.json');
runScene(config);


function runScene(config: SceneConfig) {
    let projectScene: Scene = new Scene();
    projectScene.buildBasicInfo(config);
    projectScene.buildScene4HarmonyProject();
    projectScene.inferTypes();
    
    let files: ArkFile[] = projectScene.getFiles();
    for (const arkFile of files) {
        let arkStr = "";
        let ArkClasses = arkFile.getClasses();
        for (const clazz of ArkClasses) {
            arkStr += "\n================"+clazz.getName()+"================"+"\n";
            for (const method of clazz.getMethods(true)) {
                if(method.getCfg() != undefined){
                    for(const unit of method.getCfg()!.getStmts()){
                        arkStr += unit.toString()+"\n";
                    }
                }
            }
            
        }
        
        let printer = new PrinterBuilder();
        try{
            // output dot file
            printer.dumpToDot(arkFile, "./out/print/dot/"+config.getTargetProjectName()+"/"+arkFile.getName()+"_dump.dot");
            // output json file
            printer.dumpToJson(arkFile, "./out/print/json/"+config.getTargetProjectName()+"/"+arkFile.getName()+"_dump.json");
            // output ts file
            printer.dumpToTs(arkFile, "./out/print/ts/"+config.getTargetProjectName()+"/"+arkFile.getName()+"_dump.ts");

            // output IR file
            let fileName = "./out/print/IR/"+config.getTargetProjectName()+"/"+arkFile.getName()+"_dump.txt"
            fs.mkdirSync(path.dirname(fileName), { recursive: true });
            fs.writeFileSync(fileName, arkStr);
        }catch (error) {
            console.log("an error occured in dumpping file.");
        }
        
    }
}

