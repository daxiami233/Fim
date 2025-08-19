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

import { ArkClass, ArkFile, ArkMethod, ArkNamespace, CallGraph, MethodSignature, printCallGraphDetails, Printer, PrinterBuilder } from 'arkAnalyzer/src';
import { SceneConfig } from 'arkAnalyzer/src/Config';
import { Scene } from 'arkAnalyzer/src/Scene';

let config: SceneConfig = new SceneConfig();

// build from json
config.buildFromJson("./tests/customTest/AppTestConfig.json");
// console.log("config: " + JSON.stringify(config));

function runScene4Json(config: SceneConfig) {
    let projectScene: Scene = new Scene();
    projectScene.buildBasicInfo(config);
    projectScene.buildScene4HarmonyProject();
    projectScene.inferTypes();

    printCGCHA(projectScene)
    
}

runScene4Json(config);

function printCGCHA(projectScene: Scene) {
    let methods: ArkMethod[] = projectScene.getMethods();
    let entryPoints:  MethodSignature[] = methods.map(method => method.getSignature());
    let callGraph = projectScene.makeCallGraphCHA(entryPoints);

    let calls = callGraph.getDynEdges();
    calls.forEach((callees, caller) => {
        console.log(`\nCaller: ${caller}`);
        callees.forEach((callee) => {
            console.log(`  Callee: ${callee}`);
        });
    });
}
