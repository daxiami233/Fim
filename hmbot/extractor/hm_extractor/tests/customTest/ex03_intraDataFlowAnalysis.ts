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

import { ArkClass, ArkFile, ArkMethod, ArkNamespace, CallGraph, MethodSignature, printCallGraphDetails, Printer, PrinterBuilder, StaticSingleAssignmentFormer, ArkBody, ArkStaticInvokeExpr, ArkInstanceFieldRef, ArkInstanceInvokeExpr } from 'arkAnalyzer/src';
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
    // SSAObserve(projectScene);
    // getDefUse(projectScene);
    ruleCheck(projectScene);
    
}

runScene4Json(config);

function SSAObserve(projectScene: Scene) {
    
    let staticSingleAssignmentFormer = new StaticSingleAssignmentFormer();
    let methods: ArkMethod[] = projectScene.getMethods();
    const arkMethod: ArkMethod = methods[0];
    let body = arkMethod.getBody();
    if(body!=undefined){
        console.log(body);
        staticSingleAssignmentFormer.transformBody(body)
        console.log("-----------------");
        console.log(body);
    }
}

function getDefUse(projectScene: Scene) {
    let methods: ArkMethod[] = projectScene.getMethods();
    for (let i = 0; i < methods.length; i++) {
        const arkMethod: ArkMethod = methods[i];
        const cfg = arkMethod.getBody()?.getCfg();
        cfg?.buildDefUseChain(); 
        const chains = cfg?.getDefUseChains();
        console.log(arkMethod.getSignature().toString());
        console.log(chains);
        if(chains && chains.length > 0) {
            break;
        }
    }
}
    
function ruleCheck(projectScene: Scene) {
    let methods: ArkMethod[] = projectScene.getMethods();
    for (let i = 0; i < methods.length; i++) {
        const arkMethod: ArkMethod = methods[i];
        if(arkMethod.getCfg() == undefined) {
            continue;
        }
        for (const stmt of arkMethod.getCfg()!.getStmts()) { 
            if (stmt.getExprs().length > 0) { 
                const expr = stmt.getExprs()[0]; 
                if (expr instanceof ArkInstanceInvokeExpr &&
                    expr.getMethodSignature().getMethodSubSignature().getMethodName() == "concatDate") {
                    const args = expr.getArgs(); 
                    console.log(args);
                } 
            }
        }
    }
}

