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

import { ArkClass, ArkFile, ArkMethod, ArkNamespace, CallGraph, MethodSignature, printCallGraphDetails, Printer, PrinterBuilder, StaticSingleAssignmentFormer, ArkBody, ArkStaticInvokeExpr, ArkInstanceFieldRef, ArkInstanceInvokeExpr, UndefinedVariableChecker, ModelUtils, UndefinedVariableSolver } from 'arkAnalyzer/src';
import { SceneConfig } from 'arkAnalyzer/src/Config';
import { Scene } from 'arkAnalyzer/src/Scene';

let config: SceneConfig = new SceneConfig();

// build from json
config.buildFromJson("./tests/customTest/AppTestConfig04.json");
// console.log("config: " + JSON.stringify(config));

function runScene4Json(config: SceneConfig) {
    let projectScene: Scene = new Scene();
    projectScene.buildBasicInfo(config);
    projectScene.buildScene4HarmonyProject();
    projectScene.inferTypes();
    ruleCheck(projectScene);
    
}

runScene4Json(config);

    
function ruleCheck(projectScene: Scene) {
    let files: ArkFile[] = projectScene.getFiles();
    let filenames : string[] = files.map(cls => cls.getName());
    console.log(filenames);

    let methods: ArkMethod[] = projectScene.getMethods();
    for (let i = 0; i < methods.length; i++) {
        const arkMethod: ArkMethod = methods[i];
        const problem = new
        UndefinedVariableChecker([...arkMethod.getCfg()!.getBlocks()][0].getStmts()[arkMethod.getParameters().length], arkMethod); 
        const solver = new UndefinedVariableSolver(problem, projectScene);
        solver.solve();
    }
    
}

